from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
TZ = ZoneInfo("Asia/Shanghai")


def run_python(script: Path, env: dict[str, str]) -> dict:
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {"stdout": result.stdout, "stderr": result.stderr}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def top_x_items(rows: list[dict], limit: int = 12) -> list[dict]:
    picked = [row for row in rows if row.get("text") and row.get("link")]
    picked.sort(key=lambda row: (row.get("engagement") or 0, row.get("datetime_local") or ""), reverse=True)
    return picked[:limit]


def top_wechat_items(rows: list[dict], limit: int = 10) -> list[dict]:
    picked = [row for row in rows if row.get("title") and row.get("mp_article", {}).get("url")]
    picked.sort(key=lambda row: row.get("public_time") or "", reverse=True)
    return picked[:limit]


def summarize_x(rows: list[dict]) -> list[str]:
    if not rows:
        return ["- No X posts were captured in this run."]
    topic_counts = Counter(row.get("topic") or "Other" for row in rows)
    category_counts = Counter(row.get("category") or "uncategorized" for row in rows)
    lines = [
        f"- Total matched posts: {len(rows)}",
        "- Topic mix: "
        + ", ".join(f"{topic}={count}" for topic, count in topic_counts.most_common(5)),
        "- Category mix: "
        + ", ".join(f"{category}={count}" for category, count in category_counts.most_common(5)),
    ]
    for item in top_x_items(rows):
        summary = " ".join((item.get("text") or "").split())[:180]
        lines.append(
            f"- @{item.get('username')} | {item.get('datetime_local')} | {item.get('topic')} | "
            f"{int(item.get('engagement') or 0)} | {summary} | {item.get('link')}"
        )
    return lines


def summarize_wechat(rows: list[dict]) -> list[str]:
    if not rows:
        return ["- No WeChat articles were captured in this run."]
    topic_counts = Counter()
    for row in rows:
        title_blob = " ".join(
            [
                row.get("title", ""),
                row.get("newrank", {}).get("panel_summary", ""),
                row.get("mp_article", {}).get("body_text", "")[:600],
            ]
        )
        if any(word in title_blob for word in ["OpenClaw", "Agent", "AI", "龙虾"]):
            topic_counts["AI/Agent"] += 1
        elif any(word in title_blob for word in ["芯片", "半导体", "TI", "德州仪器"]):
            topic_counts["Semiconductor"] += 1
        elif any(word in title_blob for word in ["原油", "油价", "黄金", "市场", "美股"]):
            topic_counts["Macro/Market"] += 1
        else:
            topic_counts["Other"] += 1
    lines = [
        f"- Total matched articles: {len(rows)}",
        "- Topic mix: "
        + ", ".join(f"{topic}={count}" for topic, count in topic_counts.most_common(5)),
    ]
    for item in top_wechat_items(rows):
        summary = " ".join((item.get("newrank", {}).get("panel_summary") or "").split())[:140]
        article_url = item.get("mp_article", {}).get("url", "")
        lines.append(
            f"- {item.get('title')} | {item.get('account_name')} | {item.get('public_time')} | "
            f"reads={item.get('newrank', {}).get('panel_reads') or item.get('newrank', {}).get('reads') or 'n/a'} | "
            f"{summary or 'no panel summary'} | {article_url}"
        )
    return lines


def build_report(
    hours: int,
    generated_at: datetime,
    x_payload: dict,
    wechat_payload: dict,
    x_run_meta: dict,
    wechat_run_meta: dict,
    note_lines: list[str],
) -> str:
    lines = [
        f"# Browser Social Digest ({hours}h)",
        "",
        f"- Generated at: {generated_at.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)",
        f"- X posts: {len(x_payload.get('results', []))}",
        f"- X errors: {len(x_payload.get('errors', []))}",
        f"- WeChat articles: {len(wechat_payload.get('results', []))}",
        f"- WeChat errors: {len(wechat_payload.get('errors', []))}",
        "",
        "## Run Status",
        f"- X runner output: {json.dumps(x_run_meta, ensure_ascii=False)}" if x_run_meta else "- X runner output: skipped",
        f"- WeChat runner output: {json.dumps(wechat_run_meta, ensure_ascii=False)}"
        if wechat_run_meta
        else "- WeChat runner output: skipped",
    ]
    if note_lines:
        lines.append("")
        lines.append("## Notes")
        lines.extend(note_lines)
    lines.append("")
    lines.append("## X Highlights")
    lines.extend(summarize_x(x_payload.get("results", [])))
    lines.append("")
    lines.append("## WeChat Highlights")
    lines.extend(summarize_wechat(wechat_payload.get("results", [])))
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the browser-based X + WeChat digest pipeline.")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours.")
    parser.add_argument("--skip-x", action="store_true", help="Skip the X collector.")
    parser.add_argument("--skip-wechat", action="store_true", help="Skip the WeChat collector.")
    parser.add_argument(
        "--wechat-scan-file",
        default=str(ROOT / "output" / "wechat_48h_browser_scan_v3.json"),
        help="Path to the pre-scanned Newrank candidate file.",
    )
    parser.add_argument(
        "--output-prefix",
        default="browser_social_digest",
        help="Prefix for generated files under output/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    prefix = f"{args.output_prefix}_{args.hours}h_{stamp}"

    x_json = OUTPUT_DIR / f"{prefix}_x.json"
    x_md = OUTPUT_DIR / f"{prefix}_x.md"
    wechat_json = OUTPUT_DIR / f"{prefix}_wechat.json"
    wechat_md = OUTPUT_DIR / f"{prefix}_wechat.md"
    digest_json = OUTPUT_DIR / f"{prefix}.json"
    digest_md = OUTPUT_DIR / f"{prefix}.md"

    note_lines: list[str] = []
    x_payload: dict = {"results": [], "errors": []}
    wechat_payload: dict = {"results": [], "errors": []}
    x_run_meta: dict = {}
    wechat_run_meta: dict = {}

    if not args.skip_x:
        env = os.environ.copy()
        env.update(
            {
                "X_WINDOW_HOURS": str(args.hours),
                "X_RESULT_FILE": str(x_json),
                "X_REPORT_FILE": str(x_md),
                "X_RESET_OUTPUT": "1",
            }
        )
        x_run_meta = run_python(ROOT / "scripts" / "collect_x_48h_from_browser.py", env)
        x_payload = load_json(x_json)

    if not args.skip_wechat:
        scan_file = Path(args.wechat_scan_file)
        if scan_file.exists():
            env = os.environ.copy()
            env.update(
                {
                    "WECHAT_WINDOW_HOURS": str(args.hours),
                    "WECHAT_SCAN_FILE": str(scan_file),
                    "WECHAT_RESULT_FILE": str(wechat_json),
                    "WECHAT_REPORT_FILE": str(wechat_md),
                }
            )
            wechat_run_meta = run_python(ROOT / "scripts" / "collect_wechat_48h_from_newrank.py", env)
            wechat_payload = load_json(wechat_json)
        else:
            note_lines.append(f"- WeChat scan file not found: {scan_file}")

    generated_at = datetime.now(TZ)
    digest_payload = {
        "generated_at": generated_at.isoformat(),
        "hours": args.hours,
        "x": {
            "status": x_run_meta,
            "result_file": str(x_json),
            "report_file": str(x_md),
            "payload": x_payload,
        },
        "wechat": {
            "status": wechat_run_meta,
            "result_file": str(wechat_json),
            "report_file": str(wechat_md),
            "payload": wechat_payload,
        },
        "notes": note_lines,
    }
    digest_json.write_text(json.dumps(digest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    digest_md.write_text(
        build_report(args.hours, generated_at, x_payload, wechat_payload, x_run_meta, wechat_run_meta, note_lines),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "digest_json": str(digest_json),
                "digest_md": str(digest_md),
                "x_posts": len(x_payload.get("results", [])),
                "wechat_articles": len(wechat_payload.get("results", [])),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
