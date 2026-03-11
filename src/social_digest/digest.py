from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import AppConfig, Post
from .utils import safe_filename


GENERATED_AT = "\u751f\u6210\u65f6\u95f4"
ITEM_COUNT = "\u6536\u5f55\u6761\u6570"
PLATFORM_DIST = "\u5e73\u53f0\u5206\u5e03"
OVERVIEW = "\u603b\u89c8"
NO_CONTENT = "\u5f53\u524d\u65f6\u95f4\u7a97\u53e3\u5185\u6ca1\u6709\u65b0\u5185\u5bb9"
AUTHOR = "\u4f5c\u8005"
PUBLISHED_AT = "\u53d1\u5e03\u65f6\u95f4"
LINK = "\u94fe\u63a5"
SUMMARY = "\u7b80\u4ecb"
NO_TITLE = "\u65e0\u6807\u9898"
UNKNOWN = "\u672a\u77e5"
FAILED_SOURCES = "\u6293\u53d6\u5931\u8d25"
CATEGORY_OVERVIEW = "\u5206\u7c7b\u603b\u89c8"
CATEGORY_SUMMARY = "\u7b80\u77ed\u603b\u7ed3"
ACCOUNT_COVERAGE = "\u6d89\u53ca\u8d26\u53f7"


def _format_category_name(value: str) -> str:
    mapping = {
        "ai-tech": "AI \u79d1\u6280",
        "macro-finance": "\u5b8f\u89c2\u8d22\u7ecf",
        "web3-crypto": "Web3 \u5e01\u5708",
        "uncategorized": "\u672a\u5206\u7c7b",
    }
    return mapping.get(value, value)


def _category_brief(posts: list[Post]) -> str:
    snippets: list[str] = []
    seen: set[str] = set()
    for post in sorted(posts, key=lambda item: item.published_at, reverse=True):
        snippet = (post.summary or post.content).strip()
        if not snippet or snippet in seen:
            continue
        seen.add(snippet)
        snippets.append(snippet)
        if len(snippets) == 2:
            break
    return "\uff1b".join(snippets) if snippets else NO_CONTENT


def render_digest(
    posts: list[Post],
    config: AppConfig,
    now: datetime | None = None,
    failures: list[str] | None = None,
) -> str:
    tz = ZoneInfo(config.timezone)
    now = now.astimezone(tz) if now else datetime.now(tz)
    grouped_by_source: dict[str, list[Post]] = defaultdict(list)
    grouped_by_category: dict[str, list[Post]] = defaultdict(list)
    platform_count: dict[str, int] = defaultdict(int)

    for post in sorted(posts, key=lambda item: item.published_at, reverse=True):
        grouped_by_source[post.source_name].append(post)
        grouped_by_category[post.category or "uncategorized"].append(post)
        platform_count[post.platform] += 1

    platform_dist = ", ".join(f"{name} {count} \u6761" for name, count in sorted(platform_count.items())) or "\u65e0"
    lines = [
        f"# {config.digest.title}",
        "",
        f"- {GENERATED_AT}\uff1a{now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- {ITEM_COUNT}\uff1a{len(posts)}",
        f"- {PLATFORM_DIST}\uff1a{platform_dist}",
        "",
        f"## {OVERVIEW}",
        "",
    ]

    for source_name, items in grouped_by_source.items():
        lines.append(f"- {source_name}\uff1a{len(items)} \u6761\u66f4\u65b0")

    if not grouped_by_source:
        lines.append(f"- {NO_CONTENT}")

    if grouped_by_category:
        lines.extend(["", f"## {CATEGORY_OVERVIEW}", ""])
        for category, items in grouped_by_category.items():
            authors = sorted({f"@{post.author}" for post in items})
            lines.append(
                f"- {_format_category_name(category)}\uff1a{len(items)} \u6761\u66f4\u65b0\uff0c"
                f"{len(authors)} \u4e2a KOL\uff0c{CATEGORY_SUMMARY}\uff1a{_category_brief(items)}"
            )

    for category, items in grouped_by_category.items():
        lines.extend(["", f"## {_format_category_name(category)}", ""])
        authors = sorted({f"@{post.author}" for post in items})
        lines.append(f"- {ACCOUNT_COVERAGE}\uff1a{', '.join(authors)}")
        lines.append(f"- {CATEGORY_SUMMARY}\uff1a{_category_brief(items)}")
        lines.append("")
        for post in sorted(items, key=lambda item: item.published_at, reverse=True)[: config.digest.max_items_per_source]:
            lines.extend(
                [
                    f"### @{post.author} | {post.title or NO_TITLE}",
                    f"- {PUBLISHED_AT}\uff1a{post.published_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}",
                    f"- {SUMMARY}\uff1a{post.summary or post.content[:120]}",
                    f"- {LINK}\uff1a{post.url or UNKNOWN}",
                    "",
                ]
            )

    if failures:
        lines.extend(["", f"## {FAILED_SOURCES}", ""])
        for failure in failures:
            lines.append(f"- {failure}")

    return "\n".join(lines).strip() + "\n"


def digest_output_path(output_dir: Path, title: str, now: datetime) -> Path:
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_filename(title)}.md"
    return output_dir / filename
