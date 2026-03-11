from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ..models import FetchWindow, Post
from ..source_registry import load_source_accounts
from ..utils import get_env, parse_datetime, shorten, summarize_text
from .base import Fetcher


class XBrowserFallbackError(RuntimeError):
    pass


class XTimelineFetcher(Fetcher):
    api_base = "https://api.x.com/2"

    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        strategy = str(self.source.settings.get("strategy", "api_then_browser")).strip().lower()

        if strategy in {"browser", "browser_only"}:
            return self._fetch_from_browser(window)

        try:
            return self._fetch_from_api(window)
        except Exception:
            if strategy not in {"api_then_browser", "browser_fallback"}:
                raise
            return self._fetch_from_browser(window)

    def _fetch_from_api(self, window: FetchWindow | None) -> list[Post]:
        token = get_env(str(self.source.settings.get("bearer_token_env", "")))
        if not token:
            raise ValueError(f"{self.source.name}: missing X bearer token")

        accounts = load_source_accounts(self.source, self.base_dir)
        user_ids = list(self.source.settings.get("user_ids", []))
        max_results = max(5, min(int(self.source.settings.get("max_results", 20)), 100))
        max_pages = max(1, int(self.source.settings.get("max_pages", 3)))

        headers = {"Authorization": f"Bearer {token}"}
        posts: list[Post] = []
        with httpx.Client(timeout=20.0, headers=headers) as client:
            resolved = {str(user_id): str(user_id) for user_id in user_ids}
            account_map = {account.username: account for account in accounts}
            for account in accounts:
                user_id = self._resolve_user_id(client, account.username)
                resolved[user_id] = account.username

            for user_id, username in resolved.items():
                category = account_map.get(username).category if username in account_map else "uncategorized"
                pagination_token: str | None = None
                for _ in range(max_pages):
                    params: dict[str, Any] = {
                        "max_results": max_results,
                        "tweet.fields": "created_at,lang,public_metrics",
                    }
                    if window and window.start_time:
                        params["start_time"] = window.start_time.astimezone(ZoneInfo("UTC")).isoformat()
                    if window and window.end_time:
                        params["end_time"] = window.end_time.astimezone(ZoneInfo("UTC")).isoformat()

                    excludes = []
                    if self.source.settings.get("exclude_replies", True):
                        excludes.append("replies")
                    if self.source.settings.get("exclude_reposts", True):
                        excludes.append("retweets")
                    if excludes:
                        params["exclude"] = ",".join(excludes)
                    if pagination_token:
                        params["pagination_token"] = pagination_token

                    response = client.get(f"{self.api_base}/users/{user_id}/tweets", params=params)
                    response.raise_for_status()
                    payload = response.json()

                    items = payload.get("data", [])
                    posts.extend(self._posts_from_api_items(username, category, items))
                    pagination_token = payload.get("meta", {}).get("next_token")
                    if not pagination_token:
                        break
        return self._filter_window(posts, window)

    def _posts_from_api_items(self, username: str, category: str, items: list[dict[str, Any]]) -> list[Post]:
        posts: list[Post] = []
        for item in items:
            text = (item.get("text") or "").strip()
            posts.append(
                Post(
                    source_name=self.source.name,
                    platform="x",
                    external_id=str(item["id"]),
                    url=f"https://x.com/{username}/status/{item['id']}",
                    title=shorten(text, 60),
                    content=text,
                    summary=summarize_text(text),
                    author=username,
                    published_at=parse_datetime(item.get("created_at", ""), self.timezone),
                    category=category,
                )
            )
        return posts

    def _fetch_from_browser(self, window: FetchWindow | None) -> list[Post]:
        try:
            from .x_browser import XBrowserFetcher
        except ImportError as exc:
            raise XBrowserFallbackError(
                "Browser fallback requires installing the 'browser' extra: python -m pip install -e .[browser]"
            ) from exc

        return XBrowserFetcher(self.source, self.timezone, self.base_dir).fetch(window)

    def _filter_window(self, posts: list[Post], window: FetchWindow | None) -> list[Post]:
        if not window:
            return posts

        filtered: list[Post] = []
        for post in posts:
            published = post.published_at
            if window.start_time and published < window.start_time:
                continue
            if window.end_time and published > window.end_time:
                continue
            filtered.append(post)
        return filtered

    def _resolve_user_id(self, client: httpx.Client, username: str) -> str:
        response = client.get(f"{self.api_base}/users/by/username/{username}")
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not data:
            raise ValueError(f"Unable to resolve X username: {username}")
        return str(data["id"])
