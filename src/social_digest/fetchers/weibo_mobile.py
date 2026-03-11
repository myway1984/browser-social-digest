from __future__ import annotations

import httpx

from ..models import FetchWindow, Post
from ..utils import get_env, parse_datetime, shorten, strip_html, summarize_text
from .base import Fetcher


class WeiboMobileFetcher(Fetcher):
    api_url = "https://m.weibo.cn/api/container/getIndex"

    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        uids = list(self.source.settings.get("uids", []))
        if not uids:
            raise ValueError(f"{self.source.name}: missing weibo uids")

        cookie = get_env(str(self.source.settings.get("cookie_env", "")))
        headers = {"User-Agent": "social-digest-agent/0.1"}
        if cookie:
            headers["Cookie"] = cookie

        max_results = max(1, int(self.source.settings.get("max_results", 10)))
        posts: list[Post] = []
        with httpx.Client(timeout=20.0, headers=headers) as client:
            for uid in uids:
                response = client.get(
                    self.api_url,
                    params={
                        "type": "uid",
                        "value": uid,
                        "containerid": f"107603{uid}",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                cards = payload.get("data", {}).get("cards", [])

                for card in cards[:max_results]:
                    mblog = card.get("mblog")
                    if not mblog:
                        continue
                    text = strip_html(mblog.get("text", ""))
                    user = mblog.get("user", {})
                    external_id = str(mblog.get("id") or mblog.get("idstr") or "")
                    if not external_id:
                        continue
                    post = Post(
                        source_name=self.source.name,
                        platform="weibo",
                        external_id=external_id,
                        url=f"https://m.weibo.cn/detail/{external_id}",
                        title=shorten(text, 60),
                        content=text,
                        summary=summarize_text(text),
                        author=user.get("screen_name", uid),
                        published_at=parse_datetime(mblog.get("created_at", ""), self.timezone),
                    )
                    if window and window.start_time and post.published_at < window.start_time:
                        continue
                    if window and window.end_time and post.published_at > window.end_time:
                        continue
                    posts.append(post)
        return posts
