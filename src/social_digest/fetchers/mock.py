from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import FetchWindow, Post
from ..utils import summarize_text
from .base import Fetcher


class MockFetcher(Fetcher):
    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        limit = int(self.source.settings.get("max_results", 3))
        now = datetime.now(ZoneInfo(self.timezone))
        anchor = window.end_time.astimezone(ZoneInfo(self.timezone)) if window and window.end_time else now
        posts: list[Post] = []
        for index in range(limit):
            content = (
                f"这是 {self.source.name} 的第 {index + 1} 条模拟更新。"
                "它用于验证抓取、摘要、入库和简报生成流程是否正常工作。"
            )
            posts.append(
                Post(
                    source_name=self.source.name,
                    platform=self.source.platform,
                    external_id=f"mock-{index}",
                    url=f"https://example.com/mock/{index}",
                    title=f"模拟更新 {index + 1}",
                    content=content,
                    summary=summarize_text(content),
                    author=self.source.name,
                    published_at=anchor - timedelta(minutes=index * 5),
                )
            )
        return posts
