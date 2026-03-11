from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def strip_html(value: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(value or "")
    text = stripper.get_text()
    return re.sub(r"\s+", " ", text).strip()


def shorten(value: str, limit: int = 80) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def sentence_split(value: str) -> list[str]:
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return []
    pieces = re.split(r"(?<=[。！？!?\.])\s*", value)
    return [piece.strip() for piece in pieces if piece.strip()]


def summarize_text(value: str, max_sentences: int = 2, max_chars: int = 140) -> str:
    sentences = sentence_split(value)
    if not sentences:
        return ""
    return shorten(" ".join(sentences[:max_sentences]), max_chars)


def safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "_", value).strip("_") or "digest"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_env(name: str) -> str:
    if not name:
        return ""
    return os.getenv(name, "").strip()


def parse_datetime(value: str, tz_name: str) -> datetime:
    value = (value or "").strip()
    tz = ZoneInfo(tz_name)
    if not value:
        return datetime.now(tz)

    try:
        iso_value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_value)
        return parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(value).astimezone(tz)
    except (TypeError, ValueError):
        pass

    relative = _parse_cn_relative(value, tz)
    if relative:
        return relative

    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
        except ValueError:
            continue
    return datetime.now(tz)


def _parse_cn_relative(value: str, tz: ZoneInfo) -> datetime | None:
    now = datetime.now(tz)
    patterns = [
        (r"(\d+)\s*秒前", "seconds"),
        (r"(\d+)\s*分钟前", "minutes"),
        (r"(\d+)\s*小时前", "hours"),
        (r"(\d+)\s*天前", "days"),
    ]
    for pattern, unit in patterns:
        match = re.fullmatch(pattern, value)
        if not match:
            continue
        amount = int(match.group(1))
        if unit == "seconds":
            return now - timedelta(seconds=amount)
        if unit == "minutes":
            return now - timedelta(minutes=amount)
        if unit == "hours":
            return now - timedelta(hours=amount)
        return now - timedelta(days=amount)

    if value.startswith("今天 "):
        try:
            parsed = datetime.strptime(value.removeprefix("今天 "), "%H:%M")
            return now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
        except ValueError:
            return None

    if value.startswith("昨天 "):
        try:
            parsed = datetime.strptime(value.removeprefix("昨天 "), "%H:%M")
            target = now - timedelta(days=1)
            return target.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
        except ValueError:
            return None
    return None
