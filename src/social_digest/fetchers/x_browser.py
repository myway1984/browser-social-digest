from __future__ import annotations

from datetime import timedelta

from bs4 import BeautifulSoup

from ..models import FetchWindow, Post
from ..source_registry import load_source_accounts
from ..utils import parse_datetime, shorten, summarize_text
from ..web_capture import FINAL_FAILURE_NOTE, WebCapturePipeline
from .base import Fetcher


class XBrowserFetcher(Fetcher):
    expected_markers = ["data-testid=\"tweet\"", "data-testid=\"tweetText\"", "/status/"]

    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        accounts = load_source_accounts(self.source, self.base_dir)
        max_items = max(5, int(self.source.settings.get("browser_max_items", self.source.settings.get("max_results", 20))))
        remote_profile_dir = str(self.source.settings.get("remote_debug_profile_dir", "")).strip() or None
        debug_port = int(self.source.settings.get("remote_debug_port", 9222))

        pipeline = WebCapturePipeline(self.base_dir)
        posts: list[Post] = []
        failures: list[str] = []

        for account in accounts:
            url = self._target_url(account.username, window)
            result = pipeline.capture(
                url=url,
                slug=f"x_{account.username}",
                expected_markers=self.expected_markers,
                remote_profile_dir=remote_profile_dir,
                debug_port=debug_port,
            )
            if not result.ok:
                failures.append(f"@{account.username}: {result.note}")
                continue

            extracted = self._extract_posts_from_html(result.body_html or result.html, account.username, account.category, window)
            if not extracted:
                failures.append(f"@{account.username}: {FINAL_FAILURE_NOTE}")
                continue
            posts.extend(extracted[:max_items])

        if posts:
            unique: dict[tuple[str, str], Post] = {}
            for post in posts:
                unique[(post.source_name, post.external_id)] = post
            return list(unique.values())

        reason = "; ".join(failures) if failures else FINAL_FAILURE_NOTE
        raise RuntimeError(reason)

    def _extract_posts_from_html(
        self,
        html: str,
        username: str,
        category: str,
        window: FetchWindow | None,
    ) -> list[Post]:
        soup = BeautifulSoup(html, "html.parser")
        posts: list[Post] = []
        for article in soup.select("article[data-testid='tweet']"):
            time_node = article.select_one("time")
            text_node = article.select_one("[data-testid='tweetText']")
            status_link = article.select_one("a[href*='/status/']")
            if not time_node or not text_node or not status_link:
                continue

            published_at = parse_datetime(time_node.get("datetime", ""), self.timezone)
            text = text_node.get_text(" ", strip=True)
            href = status_link.get("href", "")
            if not text or "/status/" not in href:
                continue

            external_id = href.rstrip("/").split("/")[-1]
            post = Post(
                source_name=self.source.name,
                platform="x",
                external_id=external_id,
                url=f"https://x.com{href}" if href.startswith("/") else href,
                title=shorten(text, 60),
                content=text,
                summary=summarize_text(text),
                author=username,
                published_at=published_at,
                category=category,
            )
            if window and window.start_time and post.published_at < window.start_time:
                continue
            if window and window.end_time and post.published_at > window.end_time:
                continue
            posts.append(post)
        return posts

    def _target_url(self, username: str, window: FetchWindow | None) -> str:
        if not window or not window.start_time:
            return f"https://x.com/{username}"

        start = window.start_time.strftime("%Y-%m-%d")
        end = ((window.end_time or window.start_time) + timedelta(days=1)).strftime("%Y-%m-%d")
        return f"https://x.com/search?q=(from%3A{username})%20since%3A{start}%20until%3A{end}&src=typed_query&f=live"
