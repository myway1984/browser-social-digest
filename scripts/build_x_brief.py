from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def zh(text: str) -> str:
    return text.encode("ascii").decode("unicode_escape")


def top_by_topic(results: list[dict], topic: str, count: int = 4) -> list[dict]:
    rows = [item for item in results if item.get("topic") == topic]
    rows.sort(key=lambda item: item.get("engagement", 0), reverse=True)
    return rows[:count]


def compact_text(text: str, limit: int = 120) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[:limit] + "..."


def format_item(item: dict) -> str:
    time_label = item["datetime_local"][5:16].replace("T", " ")
    return (
        f"- @{item['username']} | {time_label} | {item['link']}\n"
        f"  {compact_text(item.get('text', ''))}"
    )


def build_markdown(payload: dict) -> str:
    results = payload["results"]
    errors = payload.get("errors", [])
    user_counts = Counter(item["username"] for item in results)
    topic_counts = Counter(item.get("topic", "") for item in results)
    category_counts = Counter(item.get("category", "") for item in results)

    highlights = [
        ("AI/Agent", top_by_topic(results, "AI/Agent")),
        ("Semiconductor", top_by_topic(results, "Semiconductor")),
        ("Macro/Market", top_by_topic(results, "Macro/Market")),
    ]

    lines: list[str] = [
        "# " + zh("X 48\\u5c0f\\u65f6\\u7b80\\u62a5"),
        "",
        f"- {zh('\\u751f\\u6210\\u65f6\\u95f4\\uff1a')}{payload['generated_at']}",
        f"- {zh('\\u65f6\\u95f4\\u7a97\\u53e3\\uff1a')}{payload['cutoff']} {zh('\\u81f3')} {payload['generated_at']}",
        f"- {zh('\\u547d\\u4e2d\\u66f4\\u65b0\\uff1a')}{len(results)}",
        f"- {zh('\\u6293\\u53d6\\u5f02\\u5e38\\uff1a')}{len(errors)}",
        f"- {zh('\\u8d26\\u53f7\\u8986\\u76d6\\uff1a')}{len(user_counts)} {zh('\\u4e2a')}",
        "",
        "## " + zh("\\u603b\\u7ed3"),
        "",
        "- " + zh("AI Agent \\u4e3b\\u7ebf\\u7ee7\\u7eed\\u5347\\u6e29\\uff0c\\u4f46\\u8ba8\\u8bba\\u91cd\\u5fc3\\u5df2\\u7ecf\\u4ece\\u201c\\u80fd\\u4e0d\\u80fd\\u7528\\u201d\\u8f6c\\u5411\\u201c\\u600e\\u4e48\\u4ea7\\u54c1\\u5316\\u3001\\u600e\\u4e48\\u5b89\\u5168\\u843d\\u5730\\u3001\\u600e\\u4e48\\u548c\\u811a\\u672c\\u534f\\u540c\\u201d\\u3002"),
        "- " + zh("\\u534a\\u5bfc\\u4f53\\u4fe1\\u53f7\\u6bd4\\u4e0a\\u8f6e\\u66f4\\u5bc6\\uff0c\\u6838\\u5fc3\\u96c6\\u4e2d\\u5728 HBM\\u3001\\u6210\\u719f\\u5236\\u7a0b\\u6da8\\u4ef7\\u3001Samsung/AMD \\u6761\\u4ef6\\u4ea4\\u6362\\uff0c\\u4ee5\\u53ca Micron \\u4e1a\\u7ee9\\u548c\\u5e02\\u573a\\u9884\\u671f\\u9519\\u4f4d\\u3002"),
        "- " + zh("\\u5b8f\\u89c2\\u5c42\\u9762\\u4ecd\\u88ab\\u4e2d\\u4e1c\\u5c40\\u52bf\\u3001\\u6cb9\\u6c14\\u8bbe\\u65bd\\u6253\\u51fb\\u3001FOMC \\u548c\\u6ede\\u80c0\\u4ea4\\u6613\\u9884\\u671f\\u4e3b\\u5bfc\\uff0c\\u98ce\\u9669\\u504f\\u597d\\u5e76\\u672a\\u771f\\u6b63\\u7a33\\u5b9a\\u3002"),
        "- " + zh("\\u5c31\\u4e1a\\u4e0e\\u7ec4\\u7ec7\\u7ed3\\u6784\\u8ba8\\u8bba\\u5347\\u6e29\\uff0cAI \\u5bf9\\u5c97\\u4f4d\\u5206\\u5de5\\u3001\\u6821\\u62db\\u7ed3\\u6784\\u548c\\u201cAI \\u5168\\u6808\\u5de5\\u7a0b\\u5e08\\u201d\\u53d9\\u4e8b\\u7684\\u5f71\\u54cd\\u5f00\\u59cb\\u53d8\\u5f97\\u66f4\\u5177\\u4f53\\u3002"),
        "",
        "## " + zh("\\u7ed3\\u6784"),
        "",
        (
            "- " + zh("\\u4e3b\\u9898\\u5206\\u5e03\\uff1a") +
            f"Other {topic_counts.get('Other', 0)} / "
            f"Semiconductor {topic_counts.get('Semiconductor', 0)} / "
            f"AI-Agent {topic_counts.get('AI/Agent', 0)} / "
            f"Macro-Market {topic_counts.get('Macro/Market', 0)}"
        ),
        (
            "- " + zh("\\u8d26\\u53f7\\u7c7b\\u578b\\uff1a") +
            f"ai-tech {category_counts.get('ai-tech', 0)} / "
            f"macro-finance {category_counts.get('macro-finance', 0)}"
        ),
        "- " + zh("\\u6700\\u6d3b\\u8dc3\\u8d26\\u53f7\\uff1a") + zh("\\uff0c").join(
            f"@{username} {count}{zh('\\u6761')}" for username, count in user_counts.most_common(8)
        ),
        "",
        "## " + zh("\\u91cd\\u70b9\\u4e3b\\u7ebf"),
        "",
        "### 1. OpenClaw / Claude / GPT-5.4",
        "",
        "- " + zh("OpenAI \\u5728 3 \\u6708 18 \\u65e5\\u53d1\\u5e03 GPT-5.4 mini\\uff0c\\u5e76\\u540c\\u6b65\\u8fdb\\u5165 ChatGPT\\u3001Codex \\u548c API\\uff0c\\u628a\\u66f4\\u5feb\\u7684 coding\\u3001computer use \\u548c subagents \\u63a8\\u6210\\u4e86\\u5e73\\u53f0\\u7ea7\\u4fe1\\u53f7\\u3002"),
        "- " + zh("OpenClaw \\u751f\\u6001\\u91cc\\u6700\\u503c\\u5f97\\u770b\\u7684\\u4e0d\\u662f\\u5355\\u4e00 demo\\uff0c\\u800c\\u662f\\u5b89\\u5168\\u3001\\u811a\\u672c\\u534f\\u540c\\u548c\\u5546\\u4e1a\\u5316\\u6848\\u4f8b\\uff1a\\u65e2\\u6709\\u4eba\\u5728\\u5356\\u54a8\\u8be2\\u4ea4\\u4ed8\\uff0c\\u4e5f\\u6709\\u4eba\\u5f00\\u59cb\\u51fa\\u5b89\\u5168\\u5b9e\\u8df5\\u6307\\u5357\\u3002"),
        "- " + zh("\\u4e2d\\u6587\\u5708\\u5f00\\u59cb\\u66f4\\u660e\\u786e\\u5730\\u533a\\u5206\\u201c\\u811a\\u672c\\u4f18\\u5148\\u201d\\u548c\\u201cAgent \\u4f18\\u5148\\u201d\\u7684\\u8fb9\\u754c\\uff0c\\u8fd9\\u8bf4\\u660e\\u843d\\u5730\\u9636\\u6bb5\\u6b63\\u5728\\u4ece\\u60c5\\u7eea\\u9a71\\u52a8\\u8f6c\\u5230\\u65b9\\u6cd5\\u8bba\\u5206\\u5316\\u3002"),
        "",
        "### 2. " + zh("\\u534a\\u5bfc\\u4f53") + " / HBM / " + zh("\\u6210\\u719f\\u5236\\u7a0b"),
        "",
        "- " + zh("jukan05 \\u8fd9\\u8f6e\\u6700\\u5f3a\\uff0c\\u8fde\\u7eed\\u628a Micron\\u3001HBM\\u3001Samsung Foundry \\u4e0e AMD \\u6761\\u4ef6\\u4ea4\\u6362\\u3001\\u4ee5\\u53ca\\u6210\\u719f\\u5236\\u7a0b\\u6da8\\u4ef7\\u4e32\\u6210\\u4e86\\u4e00\\u6761\\u5b8c\\u6574\\u4ea7\\u4e1a\\u94fe\\u53d9\\u4e8b\\u3002"),
        "- " + zh("\\u5e02\\u573a\\u60c5\\u7eea\\u4e0a\\u51fa\\u73b0\\u201c\\u4e1a\\u7ee9\\u5f3a\\u4f46\\u80a1\\u4ef7\\u4e0d\\u6da8\\u201d\\u7684\\u5206\\u6b67\\uff0c\\u8bf4\\u660e\\u534a\\u5bfc\\u4f53\\u4ea4\\u6613\\u5f00\\u59cb\\u4ece\\u5355\\u7eaf\\u8ffd\\u666f\\u6c14\\u5207\\u5230\\u535a\\u5f08\\u9884\\u671f\\u4e0a\\u9650\\u3002"),
        "- " + zh("GTC \\u4f59\\u6ce2\\u4ecd\\u5728\\u6269\\u6563\\uff0c\\u5b58\\u50a8\\u88ab\\u91cd\\u65b0\\u5b9a\\u4e49\\u4e3a AI \\u57fa\\u7840\\u8bbe\\u65bd\\u6838\\u5fc3\\u90e8\\u4ef6\\uff0c\\u800c\\u4e0d\\u662f\\u4f20\\u7edf\\u4f4e\\u9644\\u52a0\\u503c\\u914d\\u5957\\u3002"),
        "",
        "### 3. " + zh("\\u4e2d\\u4e1c\\u51b2\\u7a81") + " / " + zh("\\u6cb9\\u6c14") + " / FOMC",
        "",
        "- " + zh("qinbafrank \\u8fd9\\u8f6e\\u628a\\u4e2d\\u4e1c\\u5347\\u7ea7\\u94fe\\u6761\\u76ef\\u5f97\\u6700\\u7d27\\uff0c\\u91cd\\u70b9\\u5728\\u4f0a\\u6717\\u80fd\\u6e90\\u8bbe\\u65bd\\u3001\\u970d\\u5c14\\u6728\\u5179\\u76f8\\u5173\\u519b\\u4e8b\\u52a8\\u4f5c\\u548c\\u5bf9\\u6cb9\\u6c14\\u4f9b\\u7ed9\\u9884\\u671f\\u7684\\u5f71\\u54cd\\u3002"),
        "- " + zh("\\u5e02\\u573a\\u5b9a\\u4ef7\\u4ecd\\u5728\\u201c\\u5730\\u7f18\\u98ce\\u9669 + \\u901a\\u80c0 + \\u964d\\u606f\\u6682\\u505c\\u201d\\u4e4b\\u95f4\\u62c9\\u626f\\uff0cFOMC \\u7684\\u8bed\\u8a00\\u53d8\\u5316\\u5df2\\u7ecf\\u88ab\\u4e00\\u4e9b\\u8d26\\u6237\\u89e3\\u8bfb\\u4e3a\\u6ede\\u80c0\\u4ea4\\u6613\\u518d\\u5f3a\\u5316\\u3002"),
        "- " + zh("\\u56fd\\u5185\\u8d44\\u672c\\u5e02\\u573a\\u5c42\\u9762\\uff0c\\u5219\\u51fa\\u73b0\\u66f4\\u5f3a\\u7684\\u4ea7\\u4e1a\\u94fe\\u5b89\\u5168\\u548c\\u8d44\\u672c\\u56de\\u6d41\\u53d9\\u4e8b\\u3002"),
        "",
        "### 4. " + zh("\\u5c31\\u4e1a") + " / " + zh("\\u7ec4\\u7ec7") + " / AI " + zh("\\u65f6\\u4ee3\\u5206\\u5de5"),
        "",
        "- " + zh("seclink\\u3001abskoop \\u8fd9\\u7ec4\\u6700\\u503c\\u5f97\\u770b\\uff0c\\u7126\\u70b9\\u662f\\u6821\\u62db\\u6269\\u5927\\u3001OPC \\u653f\\u7b56\\u52a0\\u7801\\uff0c\\u4ee5\\u53ca\\u4e2d\\u56fd\\u5c31\\u4e1a\\u5e02\\u573a\\u7684 AI \\u66ff\\u4ee3\\u53ef\\u89c6\\u5316\\u3002"),
        "- " + zh("\\u8fd9\\u7c7b\\u5185\\u5bb9\\u7684\\u4ef7\\u503c\\u4e0d\\u5728\\u60c5\\u7eea\\uff0c\\u800c\\u5728\\u4e8e\\u5b83\\u628a\\u201cAI \\u5c06\\u6539\\u53d8\\u5c97\\u4f4d\\u201d\\u4ece\\u62bd\\u8c61\\u547d\\u9898\\u63a8\\u8fdb\\u5230\\u53ef\\u91cf\\u5316\\u3001\\u53ef\\u7b5b\\u9009\\u7684\\u5c42\\u9762\\u3002"),
        "",
        "## " + zh("\\u4ee3\\u8868\\u66f4\\u65b0"),
        "",
    ]

    for topic, items in highlights:
        lines.append(f"### {topic}")
        lines.append("")
        lines.extend(format_item(item) for item in items)
        lines.append("")

    lines.extend(
        [
            "## " + zh("\\u5efa\\u8bae\\u660e\\u5929\\u7ee7\\u7eed\\u76ef"),
            "",
            "- @steipete" + zh("\\uff1aOpenClaw \\u5b98\\u65b9\\u53e3\\u5f84\\u3001\\u53cd\\u8bc8\\u9a97\\u3001\\u5b89\\u5168\\u548c\\u771f\\u5b9e\\u53ef\\u7528\\u6027\\u3002"),
            "- @jukan05" + zh("\\uff1aHBM\\u3001Micron\\u3001Samsung Foundry\\u3001AMD\\u3001\\u6210\\u719f\\u5236\\u7a0b\\u4ef7\\u683c\\u3002"),
            "- @qinbafrank" + zh("\\uff1a\\u4e2d\\u4e1c\\u5c40\\u52bf\\u662f\\u5426\\u7ee7\\u7eed\\u5f80\\u80fd\\u6e90\\u8bbe\\u65bd\\u548c\\u6d77\\u5ce1\\u98ce\\u9669\\u5347\\u7ea7\\u3002"),
            "- @seclink " + zh("\\u4e0e") + " @abskoop" + zh("\\uff1aAI \\u5bf9\\u5c97\\u4f4d\\u548c\\u5c31\\u4e1a\\u5e02\\u573a\\u7684\\u91cf\\u5316\\u5f71\\u54cd\\u3002"),
            "- @OpenAI" + zh("\\uff1aGPT-5.4 mini / nano \\u540e\\u7eed\\u52a8\\u4f5c\\u4e0e\\u5f00\\u53d1\\u8005\\u53cd\\u9988\\u3002"),
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/build_x_brief.py <input_json> <output_md>")
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.write_text(build_markdown(payload), encoding="utf-8-sig")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
