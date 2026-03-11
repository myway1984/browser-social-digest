from __future__ import annotations

import tomllib
from pathlib import Path

from .models import AppConfig, DeliveryConfig, DigestConfig, EmailConfig, SourceConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    app = raw.get("app", {})
    digest = raw.get("digest", {})
    delivery = raw.get("delivery", {})
    email = delivery.get("email", {})

    sources = []
    for source in raw.get("sources", []):
        settings = {
            key: value
            for key, value in source.items()
            if key not in {"name", "platform", "enabled"}
        }
        sources.append(
            SourceConfig(
                name=source["name"],
                platform=source["platform"],
                enabled=source.get("enabled", True),
                settings=settings,
            )
        )

    return AppConfig(
        config_path=config_path,
        base_dir=config_path.parent,
        timezone=app.get("timezone", "Asia/Shanghai"),
        database_path=(config_path.parent / app.get("database_path", "data/social_digest.db")).resolve(),
        poll_interval_minutes=int(app.get("poll_interval_minutes", 30)),
        digest=DigestConfig(
            send_every_minutes=int(digest.get("send_every_minutes", 720)),
            lookback_hours=int(digest.get("lookback_hours", 24)),
            max_items_per_source=int(digest.get("max_items_per_source", 8)),
            title=digest.get("title", "社交媒体追踪简报"),
        ),
        delivery=DeliveryConfig(
            output_dir=(config_path.parent / delivery.get("output_dir", "output")).resolve(),
            write_markdown=bool(delivery.get("write_markdown", True)),
            print_to_console=bool(delivery.get("print_to_console", False)),
            email=EmailConfig(
                enabled=bool(email.get("enabled", False)),
                smtp_host=email.get("smtp_host", ""),
                smtp_port=int(email.get("smtp_port", 465)),
                username=email.get("username", ""),
                password_env=email.get("password_env", ""),
                from_addr=email.get("from_addr", ""),
                to_addrs=list(email.get("to_addrs", [])),
                use_ssl=bool(email.get("use_ssl", True)),
            ),
        ),
        sources=sources,
    )
