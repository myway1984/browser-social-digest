from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import Browser, BrowserContext, Error, Page, TimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SCAN_FILE = Path(os.getenv("WECHAT_SCAN_FILE", ROOT / "output" / "wechat_48h_browser_scan_v3.json"))
RESULT_FILE = Path(os.getenv("WECHAT_RESULT_FILE", ROOT / "output" / "wechat_48h_newrank_articles.json"))
REPORT_FILE = Path(os.getenv("WECHAT_REPORT_FILE", ROOT / "output" / "wechat_48h_newrank_report.md"))

CDP_URL = os.getenv("WECHAT_CDP_URL", "http://127.0.0.1:9222")
TZ = ZoneInfo("Asia/Shanghai")

DETAIL_URL = "https://www.newrank.cn/new/readDetial?account={account}"
DETAIL_API = "https://gw.newrank.cn/api/wechat/xdnphb/detail/v1/rank/article/lists"
DETAIL_URL_API = "https://pre-gw.newrank.cn/api/mainRank/nr/mainRank/hotContent/getDetailUrl"
TITLE_SELECTOR = ".new-title--ytp-k span"

LATEST_LABEL = "\u6700\u65b0\u6700\u70ed"
ORIGINAL_PREFIX = "\u539f\u521b"
SUMMARY_LABEL = "\u6458\u8981"
ORIGINAL_LINK_LABEL = "\u539f\u6587\u94fe\u63a5"
ANALYSIS_LABEL = "\u5185\u5bb9\u5206\u6790"
READS_LABEL = "\u9605\u8bfb\u6570"
WATCHING_LABEL = "\u5728\u770b"
LIKES_LABEL = "\u70b9\u8d5e"
COMMENTS_LABEL = "\u7559\u8a00(\u542b\u56de\u590d)"
REWARDS_LABEL = "\u8d5e\u8d4f\u6570"
WORDS_LABEL = "\u5185\u5bb9\u5b57\u6570"
HOTSPOTS_LABEL = "\u6d89\u53ca\u70ed\u70b9"
COMMENT_ANALYSIS_LABEL = "\u7559\u8a00\u5206\u6790"
MORE_COMMENTS_LABEL = "\u66f4\u591a\u7559\u8a00"
PREV_LABEL = "\u4e0a\u4e00\u7bc7"
NEXT_LABEL = "\u4e0b\u4e00\u7bc7"


@dataclass
class CandidateArticle:
    account_name: str
    account_handle: str
    public_time: str
    title: str


def newrank_token() -> str:
    token = os.getenv("WECHAT_NEWRANK_TOKEN", "").strip() or os.getenv("WECHAT_NEWrank_TOKEN", "").strip()
    if not token:
        raise RuntimeError("missing WECHAT_NEWRANK_TOKEN")
    return token


def normalize_title(title: str) -> str:
    value = re.sub(r"\s+", "", title or "")
    if value.startswith(ORIGINAL_PREFIX):
        value = value[len(ORIGINAL_PREFIX) :]
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    return value.strip()


def window_hours() -> int:
    raw = os.getenv("WECHAT_WINDOW_HOURS", "").strip()
    return int(raw) if raw.isdigit() else 48


def parse_scan() -> list[CandidateArticle]:
    rows = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    cutoff = datetime.now(TZ) - timedelta(hours=window_hours())
    picked: list[CandidateArticle] = []
    for account in rows:
        account_url = account.get("account_url", "")
        handle = parse_qs(urlparse(account_url).query).get("account", [""])[0]
        if not handle:
            continue
        for item in account.get("items", []):
            title = (item.get("title") or "").strip()
            public_time = (item.get("time") or "").strip()
            if title in {"", LATEST_LABEL}:
                continue
            try:
                dt = datetime.strptime(public_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
            except ValueError:
                continue
            if dt < cutoff:
                continue
            picked.append(
                CandidateArticle(
                    account_name=account.get("account_name", handle),
                    account_handle=handle,
                    public_time=public_time,
                    title=title,
                )
            )
    return picked


def pick_context(browser: Browser) -> BrowserContext:
    if browser.contexts:
        return browser.contexts[0]
    return browser.new_context()


def pick_control_page(context: BrowserContext) -> Page:
    for page in context.pages:
        if "newrank.cn" in page.url:
            return page
    page = context.new_page()
    page.goto("https://www.newrank.cn/", wait_until="domcontentloaded")
    return page


def fetch_article_list(page: Page, account_handle: str) -> list[dict[str, Any]]:
    token = newrank_token()
    payload = page.evaluate(
        """async ({api, account, token}) => {
            const response = await fetch(api, {
              method: 'POST',
              headers: {
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'n-token': token
              },
              body: `account=${encodeURIComponent(account)}`,
              credentials: 'include'
            });
            return await response.json();
        }""",
        {"api": DETAIL_API, "account": account_handle, "token": token},
    )
    value = payload.get("value") or {}
    hot_articles = value.get("hotArticles") or []
    flattened: list[dict[str, Any]] = []
    for group in hot_articles:
        if isinstance(group, list):
            flattened.extend(group)
    return flattened


def wait_for_mp_popup(page: Page) -> Page | None:
    existing_pages = set(page.context.pages)
    for _ in range(40):
        page.wait_for_timeout(250)
        new_pages = [p for p in page.context.pages if p not in existing_pages]
        for popup in new_pages:
            if "mp.weixin.qq.com" in popup.url:
                return popup
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=4000)
            except TimeoutError:
                pass
            if "mp.weixin.qq.com" in popup.url:
                return popup
    return None


def decrypt_newrank_url(ciphertext: str) -> str:
    js = f"""
const crypto = require('crypto');
const key = Buffer.from('cdxbxhs147258369', 'utf8');
const decipher = crypto.createDecipheriv('aes-128-ecb', key, null);
decipher.setAutoPadding(true);
let out = decipher.update('{ciphertext}', 'base64', 'utf8');
out += decipher.final('utf8');
process.stdout.write(out);
"""
    result = subprocess.run(
        ["node", "-e", js],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def fallback_mp_page(page: Page, article_uuid: str) -> Page:
    token = newrank_token()
    payload = page.evaluate(
        """async ({api, photoId, token}) => {
            const response = await fetch(api, {
              method: 'POST',
              headers: {
                'content-type': 'application/json',
                'n-token': token
              },
              body: JSON.stringify({platform: 0, photoId}),
              credentials: 'include'
            });
            return await response.json();
        }""",
        {"api": DETAIL_URL_API, "photoId": article_uuid, "token": token},
    )
    encrypted_url = payload.get("data") or ""
    if not encrypted_url:
        raise RuntimeError(f"missing encrypted mp url: {payload}")
    mp_url = decrypt_newrank_url(encrypted_url)
    mp_page = page.context.new_page()
    mp_page.goto(mp_url, wait_until="domcontentloaded")
    mp_page.wait_for_timeout(2500)
    return mp_page


def extract_after_label(compact_text: str, label: str, stop_labels: list[str]) -> str:
    pattern = re.escape(label) + r"(.*?)" + r"(?:" + "|".join(re.escape(x) for x in stop_labels) + r")"
    match = re.search(pattern, compact_text)
    return match.group(1).strip() if match else ""


def extract_single_metric(compact_text: str, label: str) -> str:
    pattern = re.escape(label) + r"\s*([0-9\+\u4e07\.]+)"
    match = re.search(pattern, compact_text)
    return match.group(1).strip() if match else ""


def extract_detail_panel(page: Page) -> dict[str, Any]:
    raw_text = page.evaluate("() => document.body.innerText")
    title = page.locator(TITLE_SELECTOR).inner_text(timeout=5000).strip()
    compact = re.sub(r"\s+", " ", raw_text)
    return {
        "panel_title": title,
        "panel_text": raw_text,
        "summary": extract_after_label(compact, SUMMARY_LABEL, [ORIGINAL_LINK_LABEL, ANALYSIS_LABEL]),
        "reads": extract_single_metric(compact, READS_LABEL),
        "watching": extract_single_metric(compact, WATCHING_LABEL),
        "likes": extract_single_metric(compact, LIKES_LABEL),
        "comments": extract_single_metric(compact, COMMENTS_LABEL),
        "rewards": extract_single_metric(compact, REWARDS_LABEL),
        "content_words": extract_single_metric(compact, WORDS_LABEL),
        "hotspots": extract_after_label(
            compact,
            HOTSPOTS_LABEL,
            [COMMENT_ANALYSIS_LABEL, MORE_COMMENTS_LABEL, PREV_LABEL, NEXT_LABEL],
        ),
    }


def extract_mp_article(page: Page) -> dict[str, Any]:
    page.wait_for_load_state("domcontentloaded", timeout=10000)
    page.wait_for_timeout(2500)
    return page.evaluate(
        """() => {
            const q = (sel) => document.querySelector(sel)?.innerText?.trim() || '';
            const body = document.querySelector('#js_content');
            return {
              url: location.href,
              title: q('#activity-name'),
              author: q('#js_name'),
              publish_time: q('#publish_time'),
              body_text: body ? body.innerText.replace(/\\s+/g, ' ').trim() : '',
              body_html_length: body ? body.innerHTML.length : 0
            };
        }"""
    )


def find_card_id(page: Page, wanted_title: str) -> str:
    return page.evaluate(
        """({wantedTitle, originalPrefix}) => {
            const items = Array.from(document.querySelectorAll('[id^="catalog"]'));
            const normalize = (text) => {
              let value = (text || '').replace(/\\s+/g, '');
              if (value.startsWith(originalPrefix)) {
                value = value.slice(originalPrefix.length);
              }
              return value.replace(/[\\u201c\\u201d]/g, '"').replace(/[\\u2018\\u2019]/g, "'");
            };
            const hit = items.find((node) => {
              const text = normalize(node.innerText || '');
              return text.includes(wantedTitle);
            });
            return hit ? hit.id : '';
        }""",
        {
            "wantedTitle": wanted_title,
            "originalPrefix": ORIGINAL_PREFIX,
        },
    )


def collect_one(page: Page, candidate: CandidateArticle) -> dict[str, Any]:
    articles = fetch_article_list(page, candidate.account_handle)
    wanted_title = normalize_title(candidate.title)
    target = next(
        (
            article
            for article in articles
            if (
                normalize_title(str(article.get("title") or "")) == wanted_title
                or normalize_title(str(article.get("title") or "")).find(wanted_title) >= 0
                or wanted_title.find(normalize_title(str(article.get("title") or ""))) >= 0
            )
            and article.get("publicTime") == candidate.public_time
        ),
        None,
    )
    if not target:
        raise RuntimeError(f"article not found in list api: {candidate.account_handle} {candidate.title}")

    page.goto(DETAIL_URL.format(account=candidate.account_handle), wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    matched_id = find_card_id(page, wanted_title)
    if not matched_id:
        raise RuntimeError(f"article card not found in detail page: {candidate.account_handle} {candidate.title}")

    item = page.locator(f"#{matched_id}")
    item.wait_for(state="visible", timeout=15000)
    item.click()
    page.wait_for_timeout(1800)
    panel = extract_detail_panel(page)

    title = page.locator(TITLE_SELECTOR)
    title.wait_for(state="visible", timeout=10000)
    before_count = len(page.context.pages)
    title.click()
    mp_page = wait_for_mp_popup(page)
    if mp_page is None:
        current_count = len(page.context.pages)
        if current_count == before_count:
            mp_page = fallback_mp_page(page, str(target.get("uuid") or ""))
        else:
            raise RuntimeError(f"popup created but mp page not ready: {candidate.title}")

    article = extract_mp_article(mp_page)
    if not article.get("body_text"):
        raise RuntimeError(f"empty mp article body: {candidate.title}")

    result = {
        "account_name": candidate.account_name,
        "account_handle": candidate.account_handle,
        "public_time": candidate.public_time,
        "title": candidate.title,
        "newrank": {
            "reads": target.get("clicksCount"),
            "likes": target.get("likeCount"),
            "panel_summary": panel.get("summary", ""),
            "panel_reads": panel.get("reads", ""),
            "panel_watching": panel.get("watching", ""),
            "panel_likes": panel.get("likes", ""),
            "panel_comments": panel.get("comments", ""),
            "panel_rewards": panel.get("rewards", ""),
            "content_words": panel.get("content_words", ""),
            "hotspots": panel.get("hotspots", ""),
        },
        "mp_article": article,
    }
    if mp_page != page:
        try:
            mp_page.close()
        except Error:
            pass
    return result


def summarize_text(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def classify(article: dict[str, Any]) -> str:
    blob = " ".join(
        [
            article["title"],
            article["newrank"].get("panel_summary", ""),
            article["mp_article"].get("body_text", "")[:1200],
        ]
    )
    checks = [
        ("\u5b8f\u89c2/\u5e02\u573a", ["\u539f\u6cb9", "\u6cb9\u4ef7", "\u9ed1\u8272\u661f\u671f\u4e00", "\u5e02\u573a", "\u7f8e\u80a1", "\u5173\u7a0e", "\u9ec4\u91d1", "\u77f3\u6cb9\u50a8\u5907"]),
        ("AI/Agent", ["OpenClaw", "AI", "\u9f99\u867e", "\u81ea\u5a92\u4f53", "\u4ee3\u7801", "\u7a0b\u5e8f\u5458", "\u8868\u683c"]),
        ("\u534a\u5bfc\u4f53", ["\u82af\u7247", "TI", "\u5fb7\u5dde\u4eea\u5668", "\u534a\u5bfc\u4f53", "\u6da8\u4ef7", "\u97e9\u56fd"]),
    ]
    for label, keywords in checks:
        if any(word in blob for word in keywords):
            return label
    return "\u5176\u4ed6"


def build_report(results: list[dict[str, Any]]) -> str:
    now = datetime.now(TZ)
    cutoff = now - timedelta(hours=window_hours())
    lines = [
        f"# WeChat Newrank Updates ({window_hours()}h)",
        "",
        f"- Generated at: {now.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)",
        f"- Time window: {cutoff.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Matched articles: {len(results)}",
        "",
    ]
    for article in results:
        lines.extend(
            [
                f"## {article['title']}",
                f"- \u516c\u4f17\u53f7: {article['account_name']} ({article['account_handle']})",
                f"- \u53d1\u5e03\u65f6\u95f4: {article['public_time']}",
                f"- \u4e3b\u9898: {classify(article)}",
                f"- \u65b0\u699c\u6570\u636e: \u9605\u8bfb {article['newrank'].get('panel_reads') or article['newrank'].get('reads')}, \u5728\u770b {article['newrank'].get('panel_watching')}, \u70b9\u8d5e {article['newrank'].get('panel_likes')}, \u7559\u8a00 {article['newrank'].get('panel_comments')}",
                f"- \u6458\u8981: {article['newrank'].get('panel_summary') or '\u65e0'}",
                f"- \u539f\u6587\u94fe\u63a5: {article['mp_article'].get('url')}",
                f"- \u539f\u6587\u63d0\u8981: {summarize_text(article['mp_article'].get('body_text', ''))}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    candidates = parse_scan()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
        context = pick_context(browser)
        page = pick_control_page(context)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for candidate in candidates:
            try:
                results.append(collect_one(page, candidate))
            except (Error, RuntimeError) as exc:
                errors.append(
                    {
                        "account_name": candidate.account_name,
                        "account_handle": candidate.account_handle,
                        "title": candidate.title,
                        "public_time": candidate.public_time,
                        "error": str(exc),
                    }
                )
        browser.close()

    output = {
        "generated_at": datetime.now(TZ).isoformat(),
        "results": results,
        "errors": errors,
    }
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(build_report(results), encoding="utf-8")
    print(json.dumps({"results": len(results), "errors": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
