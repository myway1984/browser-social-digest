from __future__ import annotations

import csv
import re
from pathlib import Path

from .models import AccountEntry, AppConfig, SourceConfig


CSV_HEADERS = ["username", "category", "display_name", "enabled", "notes"]
WECHAT_CSV_HEADERS = ["account_name", "category", "search_keyword", "seed_url", "enabled", "notes"]
DEFAULT_WECHAT_ACCOUNTS_FILE = "sources/wechat_accounts.csv"


def resolve_accounts_file(config: AppConfig, source: SourceConfig) -> Path:
    raw_path = str(source.settings.get("accounts_file", "")).strip()
    if not raw_path:
        raise ValueError(f"Source '{source.name}' does not define accounts_file")
    return (config.base_dir / raw_path).resolve()


def resolve_wechat_accounts_file(config: AppConfig, source: SourceConfig) -> Path:
    raw_path = str(source.settings.get("accounts_file", "")).strip() or DEFAULT_WECHAT_ACCOUNTS_FILE
    return (config.base_dir / raw_path).resolve()


def load_source_accounts(source: SourceConfig, base_dir: Path | None = None) -> list[AccountEntry]:
    entries: list[AccountEntry] = []
    default_category = str(source.settings.get("default_category", "uncategorized")).strip() or "uncategorized"

    for username in source.settings.get("usernames", []):
        normalized = str(username).strip().lstrip("@")
        if normalized:
            entries.append(AccountEntry(username=normalized, category=default_category))

    raw_path = str(source.settings.get("accounts_file", "")).strip()
    if not raw_path:
        return _dedupe_accounts(entries)

    if not base_dir:
        raise ValueError(f"Source '{source.name}' requires base_dir to load accounts_file")
    path = (base_dir / raw_path).resolve()
    if not path.exists():
        return _dedupe_accounts(entries)

    if path.suffix.lower() == ".csv":
        entries.extend(_read_csv_accounts(path))
    else:
        for line in path.read_text(encoding="utf-8").splitlines():
            normalized = line.strip().lstrip("@")
            if normalized:
                entries.append(AccountEntry(username=normalized, category=default_category))
    return _dedupe_accounts(entries)


def list_accounts(config: AppConfig, source_name: str | None = None) -> tuple[SourceConfig, list[AccountEntry]]:
    source = find_x_source(config, source_name)
    return source, load_source_accounts(source, config.base_dir)


def list_wechat_accounts(config: AppConfig, source_name: str | None = None) -> tuple[SourceConfig, list[dict[str, str]]]:
    source = find_source(config, "wechat", source_name)
    return source, load_wechat_accounts(config, source)


def add_account(
    config: AppConfig,
    username: str,
    category: str = "uncategorized",
    display_name: str = "",
    notes: str = "",
    source_name: str | None = None,
) -> Path:
    normalized = username.strip().lstrip("@")
    if not normalized:
        raise ValueError("username is empty")

    source = find_x_source(config, source_name)
    path = resolve_accounts_file(config, source)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() != ".csv":
        existing = []
        if path.exists():
            existing = [line.strip().lstrip("@") for line in path.read_text(encoding="utf-8").splitlines()]
        if normalized not in existing:
            existing.append(normalized)
            path.write_text("\n".join(existing) + "\n", encoding="utf-8")
        return path

    rows = _read_csv_accounts(path) if path.exists() else []
    usernames = {row.username for row in rows}
    if normalized not in usernames:
        rows.append(
            AccountEntry(
                username=normalized,
                category=category.strip() or "uncategorized",
                display_name=display_name.strip(),
                enabled=True,
                notes=notes.strip(),
            )
        )
        _write_csv_accounts(path, rows)
    return path


def add_wechat_account(
    config: AppConfig,
    account_name: str,
    category: str = "uncategorized",
    search_keyword: str = "",
    seed_url: str = "",
    notes: str = "",
    source_name: str | None = None,
) -> Path:
    normalized = re.sub(r"\s+", " ", account_name).strip()
    if not normalized:
        raise ValueError("account_name is empty")

    source = find_source(config, "wechat", source_name)
    path = resolve_wechat_accounts_file(config, source)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = _read_wechat_accounts(path) if path.exists() else []
    existing_names = {row["account_name"] for row in rows}
    if normalized not in existing_names:
        rows.append(
            {
                "account_name": normalized,
                "category": category.strip() or "uncategorized",
                "search_keyword": (search_keyword or normalized).strip(),
                "seed_url": seed_url.strip(),
                "enabled": "true",
                "notes": notes.strip(),
            }
        )
        _write_wechat_accounts(path, rows)
    return path


def import_accounts_from_text(
    config: AppConfig,
    input_path: str | Path,
    category: str,
    source_name: str | None = None,
) -> tuple[Path, int]:
    source = find_x_source(config, source_name)
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Input file not found: {path}")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed_entries: list[AccountEntry] = []
    for line in lines:
        entry = _parse_account_line(line, category)
        if entry:
            parsed_entries.append(entry)

    accounts_path = resolve_accounts_file(config, source)
    accounts_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_csv_accounts(accounts_path) if accounts_path.exists() and accounts_path.suffix.lower() == ".csv" else []
    merged: dict[str, AccountEntry] = {item.username: item for item in existing}
    inserted = 0
    for entry in parsed_entries:
        if entry.username not in merged:
            inserted += 1
        merged[entry.username] = entry

    if accounts_path.suffix.lower() == ".csv":
        _write_csv_accounts(accounts_path, list(merged.values()))
    else:
        usernames = sorted(merged.keys())
        accounts_path.write_text("\n".join(usernames) + "\n", encoding="utf-8")
    return accounts_path, inserted


def find_x_source(config: AppConfig, source_name: str | None = None) -> SourceConfig:
    return find_source(config, "x", source_name)


def find_source(config: AppConfig, platform: str, source_name: str | None = None) -> SourceConfig:
    platform_lower = platform.lower()
    sources = [source for source in config.sources if source.platform.lower() == platform_lower]
    if not sources:
        raise ValueError(f"No {platform} source configured")
    if source_name is None:
        return sources[0]

    for source in sources:
        if source.name == source_name:
            return source
    raise ValueError(f"{platform} source not found: {source_name}")


def _read_csv_accounts(path: Path) -> list[AccountEntry]:
    rows: list[AccountEntry] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            username = (row.get("username") or "").strip().lstrip("@")
            if not username:
                continue
            enabled_value = (row.get("enabled") or "true").strip().lower()
            rows.append(
                AccountEntry(
                    username=username,
                    category=(row.get("category") or "uncategorized").strip() or "uncategorized",
                    display_name=(row.get("display_name") or "").strip(),
                    enabled=enabled_value not in {"false", "0", "no"},
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return rows


def _write_csv_accounts(path: Path, entries: list[AccountEntry]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "username": entry.username,
                    "category": entry.category,
                    "display_name": entry.display_name,
                    "enabled": "true" if entry.enabled else "false",
                    "notes": entry.notes,
                }
            )


def load_wechat_accounts(config: AppConfig, source: SourceConfig) -> list[dict[str, str]]:
    path = resolve_wechat_accounts_file(config, source)
    if not path.exists():
        return []
    return _read_wechat_accounts(path)


def _read_wechat_accounts(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            account_name = re.sub(r"\s+", " ", (row.get("account_name") or "")).strip()
            if not account_name:
                continue
            enabled_value = (row.get("enabled") or "true").strip().lower()
            if enabled_value in {"false", "0", "no"}:
                continue
            rows.append(
                {
                    "account_name": account_name,
                    "category": (row.get("category") or "uncategorized").strip() or "uncategorized",
                    "search_keyword": (row.get("search_keyword") or account_name).strip() or account_name,
                    "seed_url": (row.get("seed_url") or "").strip(),
                    "enabled": "true",
                    "notes": (row.get("notes") or "").strip(),
                }
            )
    return rows


def _write_wechat_accounts(path: Path, entries: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WECHAT_CSV_HEADERS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "account_name": entry.get("account_name", "").strip(),
                    "category": entry.get("category", "uncategorized").strip() or "uncategorized",
                    "search_keyword": entry.get("search_keyword", "").strip(),
                    "seed_url": entry.get("seed_url", "").strip(),
                    "enabled": "true" if entry.get("enabled", "true").strip().lower() not in {"false", "0", "no"} else "false",
                    "notes": entry.get("notes", "").strip(),
                }
            )


def _dedupe_accounts(entries: list[AccountEntry]) -> list[AccountEntry]:
    deduped: dict[str, AccountEntry] = {}
    for entry in entries:
        if not entry.enabled:
            continue
        deduped[entry.username] = entry
    return list(deduped.values())


def _parse_account_line(line: str, category: str) -> AccountEntry | None:
    matches = re.findall(r"@([A-Za-z0-9_]+)", line)
    if not matches:
        return None
    username = matches[-1]
    prefix = line[: line.rfind(f"@{username}")].strip()
    display_name = prefix
    if "。" in display_name:
        display_name = display_name.split("。")[-1].strip()
    if "，" in display_name and len(display_name) > 24:
        display_name = display_name.split("，")[-1].strip()
    display_name = re.sub(r"\s+", " ", display_name).strip(" ：:.-")
    return AccountEntry(
        username=username,
        category=category,
        display_name=display_name or username,
        enabled=True,
        notes=line,
    )
