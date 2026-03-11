from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import AppConfig
from .utils import ensure_parent, get_env


def deliver_markdown(report: str, output_path: Path) -> None:
    ensure_parent(output_path)
    output_path.write_text(report, encoding="utf-8-sig")


def deliver_console(report: str) -> None:
    print(report)


def deliver_email(report: str, config: AppConfig, subject: str) -> None:
    email = config.delivery.email
    password = get_env(email.password_env)
    if not email.enabled:
        return
    if not password:
        raise ValueError("Email delivery enabled but SMTP password env is empty")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email.from_addr
    message["To"] = ", ".join(email.to_addrs)
    message.set_content(report)

    if email.use_ssl:
        with smtplib.SMTP_SSL(email.smtp_host, email.smtp_port) as server:
            server.login(email.username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(email.smtp_host, email.smtp_port) as server:
            server.starttls()
            server.login(email.username, password)
            server.send_message(message)


def make_subject(config: AppConfig) -> str:
    now = datetime.now(ZoneInfo(config.timezone))
    return f"{config.digest.title} | {now.strftime('%Y-%m-%d %H:%M')}"
