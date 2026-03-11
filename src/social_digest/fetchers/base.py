from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import FetchWindow, Post, SourceConfig


class Fetcher(ABC):
    def __init__(self, source: SourceConfig, timezone: str, base_dir: Path | None = None) -> None:
        self.source = source
        self.timezone = timezone
        self.base_dir = base_dir

    @abstractmethod
    def fetch(self, window: FetchWindow | None = None) -> list[Post]:
        raise NotImplementedError
