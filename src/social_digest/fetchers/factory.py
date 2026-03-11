from __future__ import annotations

from pathlib import Path

from ..models import SourceConfig
from .base import Fetcher
from .mock import MockFetcher
from .weibo_mobile import WeiboMobileFetcher
from .wechat import WechatFetcher
from .x_api import XTimelineFetcher


def build_fetcher(source: SourceConfig, timezone: str, base_dir: Path | None = None) -> Fetcher:
    platform = source.platform.lower()
    if platform == "x":
        return XTimelineFetcher(source, timezone, base_dir)
    if platform == "weibo":
        return WeiboMobileFetcher(source, timezone, base_dir)
    if platform == "wechat":
        return WechatFetcher(source, timezone, base_dir)
    if platform == "mock":
        return MockFetcher(source, timezone, base_dir)
    raise ValueError(f"Unsupported platform: {source.platform}")
