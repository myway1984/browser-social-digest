from __future__ import annotations

import argparse
import sys

from .config import load_config
from .service import run_daemon, run_digest, run_fetch, run_once
from .source_registry import (
    add_account,
    add_wechat_account,
    import_accounts_from_text,
    list_accounts,
    list_wechat_accounts,
)
from .utils import parse_datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scheduled social digest agent")
    parser.add_argument("--config", default="config.toml", help="Path to TOML config file")

    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch_parser = subparsers.add_parser("fetch", help="Fetch new posts only")
    subparsers.add_parser("digest", help="Build digest from recent stored posts")
    run_once_parser = subparsers.add_parser("run-once", help="Fetch and deliver a digest immediately")
    subparsers.add_parser("daemon", help="Run forever with polling")
    add_x_parser = subparsers.add_parser("add-x-account", help="Append an X account to the source pool")
    list_x_parser = subparsers.add_parser("list-x-accounts", help="List X accounts from the source pool")
    import_x_parser = subparsers.add_parser("import-x-accounts", help="Import X accounts from a local text file")
    add_wechat_parser = subparsers.add_parser("add-wechat-account", help="Append a WeChat account to the source pool")
    list_wechat_parser = subparsers.add_parser("list-wechat-accounts", help="List WeChat accounts from the source pool")

    for timed_parser in (fetch_parser, run_once_parser):
        timed_parser.add_argument("--start", help="Start time, e.g. 2026-03-08T00:00:00+08:00")
        timed_parser.add_argument("--end", help="End time, e.g. 2026-03-08T23:59:59+08:00")

    add_x_parser.add_argument("--username", required=True, help="X username to add")
    add_x_parser.add_argument("--category", default="uncategorized", help="Category, e.g. ai-tech")
    add_x_parser.add_argument("--display-name", default="", help="Optional display name")
    add_x_parser.add_argument("--notes", default="", help="Optional notes")
    add_x_parser.add_argument("--source", help="Configured X source name")
    list_x_parser.add_argument("--source", help="Configured X source name")
    import_x_parser.add_argument("--input", required=True, help="Path to the local text file")
    import_x_parser.add_argument("--category", required=True, help="Category to assign, e.g. ai-tech")
    import_x_parser.add_argument("--source", help="Configured X source name")
    add_wechat_parser.add_argument("--name", required=True, help="WeChat account display name")
    add_wechat_parser.add_argument("--category", default="uncategorized", help="Category, e.g. finance")
    add_wechat_parser.add_argument("--search-keyword", default="", help="Keyword used when searching on NewRank")
    add_wechat_parser.add_argument("--seed-url", default="", help="Optional known mp.weixin article URL")
    add_wechat_parser.add_argument("--notes", default="", help="Optional notes")
    add_wechat_parser.add_argument("--source", help="Configured WeChat source name")
    list_wechat_parser.add_argument("--source", help="Configured WeChat source name")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        config = load_config(args.config)
        start_time = parse_datetime(args.start, config.timezone) if args.start else None
        end_time = parse_datetime(args.end, config.timezone) if args.end else None
        return run_fetch(args.config, start_time=start_time, end_time=end_time)
    if args.command == "digest":
        return run_digest(args.config)
    if args.command == "run-once":
        config = load_config(args.config)
        start_time = parse_datetime(args.start, config.timezone) if args.start else None
        end_time = parse_datetime(args.end, config.timezone) if args.end else None
        return run_once(args.config, start_time=start_time, end_time=end_time)
    if args.command == "daemon":
        return run_daemon(args.config)
    if args.command == "add-x-account":
        config = load_config(args.config)
        path = add_account(
            config,
            args.username,
            category=args.category,
            display_name=args.display_name,
            notes=args.notes,
            source_name=args.source,
        )
        print(f"Added @{args.username.lstrip('@')} to {path}")
        return 0
    if args.command == "list-x-accounts":
        config = load_config(args.config)
        source, accounts = list_accounts(config, args.source)
        print(f"Source: {source.name}")
        for account in accounts:
            label = account.display_name or f"@{account.username}"
            print(f"- {label} | {account.category} | @{account.username}")
        if not accounts:
            print("(empty)")
        return 0
    if args.command == "import-x-accounts":
        config = load_config(args.config)
        path, inserted = import_accounts_from_text(
            config,
            input_path=args.input,
            category=args.category,
            source_name=args.source,
        )
        print(f"Imported {inserted} accounts into {path}")
        return 0
    if args.command == "add-wechat-account":
        config = load_config(args.config)
        path = add_wechat_account(
            config,
            args.name,
            category=args.category,
            search_keyword=args.search_keyword,
            seed_url=args.seed_url,
            notes=args.notes,
            source_name=args.source,
        )
        print(f"Added {args.name} to {path}")
        return 0
    if args.command == "list-wechat-accounts":
        config = load_config(args.config)
        source, accounts = list_wechat_accounts(config, args.source)
        print(f"Source: {source.name}")
        for account in accounts:
            print(
                "- {name} | {category} | keyword={keyword}".format(
                    name=account["account_name"],
                    category=account["category"],
                    keyword=account["search_keyword"],
                )
            )
        if not accounts:
            print("(empty)")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
