from __future__ import annotations

import csv
import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import Error, TimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")

ACCOUNTS_FILE = Path(os.getenv("X_ACCOUNTS_FILE", ROOT / "sources" / "x_accounts.csv"))
RESULT_FILE = Path(os.getenv("X_RESULT_FILE", ROOT / "output" / "x_48h_browser_live.json"))
REPORT_FILE = Path(os.getenv("X_REPORT_FILE", ROOT / "output" / "x_48h_browser_live_report.md"))
CDP_URL = os.getenv("X_CDP_URL", "http://127.0.0.1:9222")


def window_hours() -> int:
    raw = os.getenv("X_WINDOW_HOURS", "").strip()
    return int(raw) if raw.isdigit() else 48


def reset_output() -> bool:
    return os.getenv("X_RESET_OUTPUT", "").strip().lower() in {"1", "true", "yes"}


def load_accounts() -> list[dict[str, str]]:
    rows = list(csv.DictReader(ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines()))
    enabled = [row for row in rows if (row.get("enabled") or "").lower() == "true"]
    offset_raw = os.getenv("X_ACCOUNT_OFFSET", "").strip()
    if offset_raw.isdigit():
        enabled = enabled[int(offset_raw) :]
    limit_raw = os.getenv("X_ACCOUNT_LIMIT", "").strip()
    if limit_raw.isdigit():
        enabled = enabled[: int(limit_raw)]
    return enabled


def target_url(username: str, start_date: str, end_date: str) -> str:
    return (
        f"https://x.com/search?q=(from%3A{username})%20since%3A{start_date}%20"
        f"until%3A{end_date}&src=typed_query&f=live"
    )


def parse_posts(page) -> list[dict]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('article[data-testid="tweet"]')).map((article) => {
          const text = article.querySelector('[data-testid="tweetText"]')?.innerText || '';
          const timeEl = article.querySelector('time');
          const linkEl = article.querySelector('a[href*="/status/"]');
          const user = article.querySelector('[data-testid="User-Name"]')?.innerText || '';
          const statNodes = Array.from(article.querySelectorAll('[role="group"] span[data-testid="app-text-transition-container"]'));
          const stats = statNodes.map((node) => node.innerText).filter(Boolean);
          return {
            text,
            datetime: timeEl?.getAttribute('datetime') || '',
            time_label: timeEl?.innerText || '',
            link: linkEl?.href || '',
            user,
            stats
          };
        })"""
    )


def wait_human(page, low_ms: int, high_ms: int) -> None:
    page.wait_for_timeout(random.randint(low_ms, high_ms))


def gentle_browse(page) -> None:
    wait_human(page, 3200, 7600)
    page.mouse.wheel(0, random.randint(450, 1150))
    wait_human(page, 1600, 3600)
    if random.random() < 0.8:
        page.mouse.wheel(0, random.randint(650, 1900))
        wait_human(page, 1800, 4200)
    if random.random() < 0.45:
        page.mouse.wheel(0, -random.randint(180, 900))
        wait_human(page, 1200, 2600)
    if random.random() < 0.25:
        page.mouse.wheel(0, random.randint(220, 700))
        wait_human(page, 1200, 2400)


def page_state(page) -> str:
    text = page.evaluate("() => document.body.innerText.slice(0, 2500)")
    lowered = text.lower()
    if "something went wrong" in lowered or "try reloading" in lowered:
        return "error"
    if "rate limit exceeded" in lowered or "try again later" in lowered:
        return "rate_limit"
    if "出现错误" in text or "请重新加载" in text:
        return "error"
    if len(text.strip()) < 40:
        return "blank"
    return "ok"


def recover_page(page) -> None:
    page.reload(wait_until="domcontentloaded", timeout=60000)
    wait_human(page, 5000, 9000)


def account_pause(page, index: int) -> None:
    wait_human(page, 4500, 12000)
    if index > 0 and index % random.randint(4, 7) == 0:
        wait_human(page, 15000, 35000)


def parse_count(value: str) -> float:
    raw = (value or "").strip().upper().replace(",", "")
    if not raw:
        return 0.0
    try:
        if raw.endswith("K"):
            return float(raw[:-1]) * 1_000
        if raw.endswith("M"):
            return float(raw[:-1]) * 1_000_000
        if raw.endswith("B"):
            return float(raw[:-1]) * 1_000_000_000
        return float(raw)
    except ValueError:
        return 0.0


def engagement_score(stats: list[str]) -> float:
    return sum(parse_count(item) for item in stats)


def classify(text: str) -> str:
    checks = [
        (
            "AI/Agent",
            ["claude code", "openclaw", "agent", "cursor", "promptfoo", "anthropic", "openai", "vibe coding"],
        ),
        (
            "Macro/Market",
            ["oil", "原油", "wti", "g7", "israel", "iran", "宏观", "美股", "通胀", "市场", "霍尔木兹"],
        ),
        (
            "Semiconductor",
            ["chip", "芯片", "ti", "德州仪器", "hbm", "asml", "semiconductor", "helium", "氦气"],
        ),
    ]
    lowered = text.lower()
    for label, keywords in checks:
        if any(keyword.lower() in lowered for keyword in keywords):
            return label
    return "Other"


def summarize(text: str, limit: int = 220) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def build_report(results: list[dict], errors: list[dict], cutoff: datetime, now: datetime) -> str:
    hours = window_hours()
    lines = [
        f"# X Browser Updates ({hours}h)",
        "",
        f"- Generated at: {now.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)",
        f"- Time window: {cutoff.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Matched posts: {len(results)}",
        f"- Accounts with errors: {len(errors)}",
        "",
    ]
    for item in results[:40]:
        lines.extend(
            [
                f"## @{item['username']} | {item['datetime_local']}",
                f"- Category: {item['category']} / {item['topic']}",
                f"- Link: {item['link']}",
                f"- Stats: {' / '.join(item['stats']) if item['stats'] else 'n/a'}",
                f"- Summary: {summarize(item['text'])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def load_existing() -> tuple[list[dict], list[dict]]:
    if reset_output() or not RESULT_FILE.exists():
        return [], []
    payload = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return payload.get("results", []), payload.get("errors", [])


def main() -> None:
    accounts = load_accounts()
    now = datetime.now(TZ)
    cutoff = now - timedelta(hours=window_hours())
    start_date = cutoff.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    results: list[dict] = []
    errors: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        page = context.new_page()
        for account_index, account in enumerate(accounts, start=1):
            username = account["username"]
            try:
                page.goto(target_url(username, start_date, end_date), wait_until="domcontentloaded", timeout=60000)
                wait_human(page, 6500, 12000)
                state = page_state(page)
                if state != "ok":
                    recover_page(page)
                    state = page_state(page)
                if state != "ok":
                    errors.append({"username": username, "error": f"page_state={state}"})
                    continue
                gentle_browse(page)
                posts = parse_posts(page)
                for post in posts:
                    dt_raw = post.get("datetime") or ""
                    if not dt_raw:
                        continue
                    try:
                        dt_utc = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    dt_local = dt_utc.astimezone(TZ)
                    if dt_local < cutoff or dt_local > now:
                        continue
                    text = (post.get("text") or "").strip()
                    if not text:
                        continue
                    results.append(
                        {
                            "username": username,
                            "display_name": account.get("display_name", ""),
                            "category": account.get("category", ""),
                            "datetime_utc": dt_utc.isoformat(),
                            "datetime_local": dt_local.isoformat(),
                            "link": post.get("link", ""),
                            "text": text,
                            "stats": post.get("stats") or [],
                            "user": post.get("user", ""),
                            "topic": classify(text),
                            "engagement": engagement_score(post.get("stats") or []),
                        }
                    )
                account_pause(page, account_index)
            except (Error, TimeoutError) as exc:
                errors.append({"username": username, "error": str(exc)})
        try:
            page.close()
        except Error:
            pass
        browser.close()

    deduped_map: dict[str, dict] = {}
    for item in results:
        key = item["link"] or f"{item['username']}|{item['datetime_utc']}|{item['text'][:80]}"
        deduped_map[key] = item
    deduped = list(deduped_map.values())
    deduped.sort(key=lambda item: (item["engagement"], item["datetime_local"]), reverse=True)

    existing_results, existing_errors = load_existing()
    merged_map: dict[str, dict] = {}
    for item in existing_results + deduped:
        key = item["link"] or f"{item['username']}|{item['datetime_utc']}|{item['text'][:80]}"
        merged_map[key] = item
    merged_results = list(merged_map.values())
    merged_results.sort(key=lambda item: (item["engagement"], item["datetime_local"]), reverse=True)

    merged_error_map: dict[str, dict] = {}
    for item in existing_errors + errors:
        key = item.get("username", "") + "|" + item.get("error", "")
        merged_error_map[key] = item
    merged_errors = list(merged_error_map.values())

    payload = {
        "generated_at": now.isoformat(),
        "cutoff": cutoff.isoformat(),
        "results": merged_results,
        "errors": merged_errors,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(build_report(merged_results, merged_errors, cutoff, now), encoding="utf-8")
    print(json.dumps({"results": len(merged_results), "errors": len(merged_errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
