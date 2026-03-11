from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import httpx

from ..models import FetchWindow, Post
from ..utils import get_env, parse_datetime, shorten, strip_html, summarize_text
from .base import Fetcher


class WechatFetcher(Fetcher):
    token_url = "https://api.weixin.qq.com/cgi-bin/token"
    material_url = "https://api.weixin.qq.com/cgi-bin/material/batchget_material"

    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        mode = str(self.source.settings.get("mode", "feed")).strip().lower()
        if mode == "feed":
            return self._filter_window(self._fetch_feed(), window)
        if mode == "material_api":
            return self._filter_window(self._fetch_material_api(), window)
        raise ValueError(f"{self.source.name}: unsupported wechat mode {mode}")

    def _fetch_feed(self) -> list[Post]:
        feed_url = str(self.source.settings.get("feed_url", "")).strip()
        if not feed_url:
            raise ValueError(f"{self.source.name}: missing feed_url")

        max_results = max(1, int(self.source.settings.get("max_results", 10)))
        with httpx.Client(timeout=20.0) as client:
            response = client.get(feed_url)
            response.raise_for_status()
            root = ET.fromstring(response.text)

        channel = root.find("channel")
        if channel is not None:
            return self._parse_rss(channel, max_results)
        return self._parse_atom(root, max_results)

    def _parse_rss(self, channel: ET.Element, max_results: int) -> list[Post]:
        posts: list[Post] = []
        for item in channel.findall("item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = strip_html(item.findtext("description") or "")
            author = (item.findtext("author") or self.source.name).strip()
            guid = (item.findtext("guid") or link or title).strip()
            pub_date = item.findtext("pubDate") or ""
            posts.append(
                Post(
                    source_name=self.source.name,
                    platform="wechat",
                    external_id=guid,
                    url=link,
                    title=title or shorten(description, 60),
                    content=description,
                    summary=summarize_text(description or title),
                    author=author,
                    published_at=parse_datetime(pub_date, self.timezone),
                )
            )
        return posts

    def _parse_atom(self, root: ET.Element, max_results: int) -> list[Post]:
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        posts: list[Post] = []
        for entry in root.findall("atom:entry", namespace)[:max_results]:
            title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
            content = strip_html(
                entry.findtext("atom:content", default="", namespaces=namespace)
                or entry.findtext("atom:summary", default="", namespaces=namespace)
                or ""
            )
            updated = entry.findtext("atom:updated", default="", namespaces=namespace)
            author = (
                entry.findtext("atom:author/atom:name", default=self.source.name, namespaces=namespace)
                or self.source.name
            )
            link_element = entry.find("atom:link", namespace)
            link = link_element.attrib.get("href", "") if link_element is not None else ""
            external_id = entry.findtext("atom:id", default="", namespaces=namespace) or link or title
            posts.append(
                Post(
                    source_name=self.source.name,
                    platform="wechat",
                    external_id=external_id,
                    url=link,
                    title=title or shorten(content, 60),
                    content=content,
                    summary=summarize_text(content or title),
                    author=author,
                    published_at=parse_datetime(updated, self.timezone),
                )
            )
        return posts

    def _fetch_material_api(self) -> list[Post]:
        app_id = get_env(str(self.source.settings.get("app_id_env", "")))
        app_secret = get_env(str(self.source.settings.get("app_secret_env", "")))
        if not app_id or not app_secret:
            raise ValueError(f"{self.source.name}: missing WeChat app credentials")

        max_results = max(1, min(int(self.source.settings.get("max_results", 10)), 20))
        with httpx.Client(timeout=20.0) as client:
            token_response = client.get(
                self.token_url,
                params={
                    "grant_type": "client_credential",
                    "appid": app_id,
                    "secret": app_secret,
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise ValueError(f"{self.source.name}: failed to obtain WeChat access token: {token_payload}")

            response = client.post(
                self.material_url,
                params={"access_token": access_token},
                content=json.dumps({"type": "news", "offset": 0, "count": max_results}, ensure_ascii=False),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

        posts: list[Post] = []
        for item in payload.get("item", []):
            media_id = str(item.get("media_id", ""))
            news_items = item.get("content", {}).get("news_item", [])
            for article in news_items:
                title = (article.get("title") or "").strip()
                digest = strip_html(article.get("digest") or article.get("content") or "")
                link = (article.get("url") or article.get("content_source_url") or "").strip()
                published = article.get("update_time") or item.get("update_time") or ""
                external_id = f"{media_id}:{title}" if media_id else (link or title)
                posts.append(
                    Post(
                        source_name=self.source.name,
                        platform="wechat",
                        external_id=external_id,
                        url=link,
                        title=title or shorten(digest, 60),
                        content=digest,
                        summary=summarize_text(digest or title),
                        author=(article.get("author") or self.source.name).strip(),
                        published_at=parse_datetime(str(published), self.timezone),
                    )
                )
        return posts

    def _filter_window(self, posts: list[Post], window: FetchWindow | None) -> list[Post]:
        if not window:
            return posts
        filtered: list[Post] = []
        for post in posts:
            if window.start_time and post.published_at < window.start_time:
                continue
            if window.end_time and post.published_at > window.end_time:
                continue
            filtered.append(post)
        return filtered
