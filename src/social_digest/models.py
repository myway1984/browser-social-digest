from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceConfig:
    name: str
    platform: str
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountEntry:
    username: str
    category: str = "uncategorized"
    display_name: str = ""
    enabled: bool = True
    notes: str = ""


@dataclass(slots=True)
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    username: str = ""
    password_env: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    use_ssl: bool = True


@dataclass(slots=True)
class DeliveryConfig:
    output_dir: Path
    write_markdown: bool = True
    print_to_console: bool = False
    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass(slots=True)
class DigestConfig:
    send_every_minutes: int = 720
    lookback_hours: int = 24
    max_items_per_source: int = 8
    title: str = "\u793e\u4ea4\u5a92\u4f53\u8ffd\u8e2a\u7b80\u62a5"


@dataclass(slots=True)
class AppConfig:
    config_path: Path
    base_dir: Path
    timezone: str
    database_path: Path
    poll_interval_minutes: int
    digest: DigestConfig
    delivery: DeliveryConfig
    sources: list[SourceConfig]


@dataclass(slots=True)
class FetchWindow:
    start_time: datetime | None = None
    end_time: datetime | None = None


@dataclass(slots=True)
class Post:
    source_name: str
    platform: str
    external_id: str
    url: str
    title: str
    content: str
    summary: str
    author: str
    published_at: datetime
    category: str = "uncategorized"
