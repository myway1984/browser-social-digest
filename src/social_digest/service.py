from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import load_config
from .delivery import deliver_console, deliver_email, deliver_markdown, make_subject
from .digest import digest_output_path, render_digest
from .fetchers import build_fetcher
from .models import AppConfig, FetchWindow, Post, SourceConfig
from .storage import Storage


class DigestService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.storage = Storage(config.database_path)
        self.last_failures: list[str] = []

    def fetch_once(self, start_time: datetime | None = None, end_time: datetime | None = None) -> list[Post]:
        inserted: list[Post] = []
        self.last_failures = []
        now = datetime.now(ZoneInfo(self.config.timezone))
        for source in self.config.sources:
            if not source.enabled:
                continue
            window = self._resolve_fetch_window(source, now, start_time, end_time)
            try:
                fetcher = build_fetcher(source, self.config.timezone, self.config.base_dir)
                inserted.extend(self.storage.upsert_posts(fetcher.fetch(window)))
                self._mark_source_fetched(source, window.end_time or now)
            except Exception as exc:
                failure = f"{source.name}\uff1a{exc}"
                self.last_failures.append(failure)
                print(f"[warn] source '{source.name}' failed: {exc}")
        return inserted

    def build_digest_for_recent_window(self) -> tuple[str, list[Post]] | None:
        tz = ZoneInfo(self.config.timezone)
        since = self._digest_since(tz)
        posts = self.storage.recent_posts(since)
        if not posts and not self.last_failures:
            return None
        return render_digest(posts, self.config, failures=self.last_failures), posts

    def build_digest_for_posts(self, posts: list[Post]) -> str | None:
        if not posts and not self.last_failures:
            return None
        return render_digest(posts, self.config, failures=self.last_failures)

    def deliver_report(self, report: str) -> None:
        now = datetime.now(ZoneInfo(self.config.timezone))
        if self.config.delivery.write_markdown:
            output_path = digest_output_path(self.config.delivery.output_dir, self.config.digest.title, now)
            deliver_markdown(report, output_path)
        if self.config.delivery.print_to_console:
            deliver_console(report)
        if self.config.delivery.email.enabled:
            deliver_email(report, self.config, make_subject(self.config))

    def digest_due(self) -> bool:
        value = self.storage.get_state("last_digest_at")
        if not value:
            return True
        last_digest_at = datetime.fromisoformat(value)
        return datetime.now(ZoneInfo(self.config.timezone)) - last_digest_at >= timedelta(
            minutes=self.config.digest.send_every_minutes
        )

    def mark_digest_sent(self) -> None:
        self.storage.set_state("last_digest_at", datetime.now(ZoneInfo(self.config.timezone)).isoformat())

    def _digest_since(self, tz: ZoneInfo) -> datetime:
        fallback = datetime.now(tz) - timedelta(hours=self.config.digest.lookback_hours)
        value = self.storage.get_state("last_digest_at")
        if not value:
            return fallback
        last_digest_at = datetime.fromisoformat(value)
        return max(fallback, last_digest_at.astimezone(tz))

    def _resolve_fetch_window(
        self,
        source: SourceConfig,
        now: datetime,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> FetchWindow:
        tz = ZoneInfo(self.config.timezone)
        resolved_end = end_time.astimezone(tz) if end_time else now
        if start_time or end_time:
            resolved_start = start_time.astimezone(tz) if start_time else None
            return FetchWindow(start_time=resolved_start, end_time=resolved_end)

        overlap_minutes = int(source.settings.get("fetch_overlap_minutes", 2))
        state_key = f"last_fetch_at::{source.name}"
        last_fetch_at = self.storage.get_state(state_key)
        if last_fetch_at:
            start = datetime.fromisoformat(last_fetch_at).astimezone(tz) - timedelta(minutes=overlap_minutes)
            return FetchWindow(start_time=start, end_time=resolved_end)

        if "window_hours" in source.settings:
            return FetchWindow(
                start_time=resolved_end - timedelta(hours=int(source.settings["window_hours"])),
                end_time=resolved_end,
            )
        return FetchWindow(end_time=resolved_end)

    def _mark_source_fetched(self, source: SourceConfig, fetched_at: datetime) -> None:
        self.storage.set_state(f"last_fetch_at::{source.name}", fetched_at.isoformat())


def run_fetch(config_path: str, start_time: datetime | None = None, end_time: datetime | None = None) -> int:
    service = DigestService(load_config(config_path))
    inserted = service.fetch_once(start_time=start_time, end_time=end_time)
    print(f"Fetched {len(inserted)} new posts.")
    return 0


def run_digest(config_path: str) -> int:
    service = DigestService(load_config(config_path))
    built = service.build_digest_for_recent_window()
    if not built:
        print("No recent posts found.")
        return 0
    report, posts = built
    service.deliver_report(report)
    print(f"Delivered digest with {len(posts)} posts.")
    return 0


def run_once(config_path: str, start_time: datetime | None = None, end_time: datetime | None = None) -> int:
    service = DigestService(load_config(config_path))
    inserted = service.fetch_once(start_time=start_time, end_time=end_time)
    report = service.build_digest_for_posts(inserted)
    if not report:
        print("No new posts found.")
        return 0
    service.deliver_report(report)
    service.mark_digest_sent()
    print(f"Fetched and delivered {len(inserted)} new posts.")
    return 0


def run_daemon(config_path: str) -> int:
    service = DigestService(load_config(config_path))
    interval_seconds = max(60, service.config.poll_interval_minutes * 60)
    while True:
        inserted = service.fetch_once()
        print(f"[{datetime.now().isoformat()}] fetched {len(inserted)} new posts")
        if service.digest_due():
            built = service.build_digest_for_recent_window()
            if built:
                report, posts = built
                service.deliver_report(report)
                service.mark_digest_sent()
                print(f"[{datetime.now().isoformat()}] delivered digest with {len(posts)} posts")
            else:
                print(f"[{datetime.now().isoformat()}] digest skipped: no recent posts")
        time.sleep(interval_seconds)
