# Browser Social Digest

Browser-based monitoring and digest generation for:

- `X` account watchlists
- `WeChat public accounts` discovered through `newrank.cn`
- structured `Markdown` and `JSON` output for downstream agents

This repo started as an internal workflow and was cleaned up into a reusable public project. The current focus is practical browser automation with a logged-in Chrome session, not a pure API-only collector.

## What It Does

The project helps you:

1. reuse a logged-in desktop Chrome session
2. read recent posts from a curated `X` account pool
3. open `newrank.cn`, inspect account detail pages, and click through to original WeChat articles
4. produce a structured digest for human reading or agent consumption

## Why Browser-Based

Many high-value sources are either rate-limited, partially blocked, or not fully accessible through stable public APIs.

This repo therefore leans on:

- `Playwright` + Chrome remote debugging
- slower, human-like page interaction for `X`
- Newrank detail-page navigation for `WeChat`
- JSON + Markdown outputs that other tools can reuse

## Current Status

What is already usable:

- browser-driven `X` scraping from a watchlist
- browser-driven `WeChat` article extraction from Newrank candidate pages
- a unified runner that writes timestamped digest files
- a reusable Codex skill under [`skills/browser-social-digest`](./skills/browser-social-digest)

What is still opinionated or workflow-dependent:

- `WeChat` currently expects a pre-scanned Newrank candidate file
- the browser session must already be logged in to `X` and `newrank.cn`
- Newrank may hit daily access caps depending on account state

## Repository Layout

```text
scripts/
  collect_x_48h_from_browser.py
  collect_wechat_48h_from_newrank.py
  run_browser_social_digest.py

skills/
  browser-social-digest/

sources/
  x_accounts.example.csv
  wechat_accounts.example.csv

src/social_digest/
  reusable Python package code
```

## Quick Start

### 1. Install

```powershell
python -m pip install -e .[browser]
python -m playwright install chromium
```

### 2. Prepare your watchlists

Copy the example files and edit them:

```powershell
Copy-Item sources\x_accounts.example.csv sources\x_accounts.csv
Copy-Item sources\wechat_accounts.example.csv sources\wechat_accounts.csv
```

### 3. Start or reuse a logged-in Chrome session

Your Chrome session should:

- be logged in to `X`
- be logged in to `newrank.cn`
- expose remote debugging, usually at `http://127.0.0.1:9222`

### 4. Set required environment variables

At minimum:

```powershell
$env:WECHAT_NEWRANK_TOKEN = "your_newrank_token"
```

Optional:

```powershell
$env:X_CDP_URL = "http://127.0.0.1:9222"
$env:WECHAT_CDP_URL = "http://127.0.0.1:9222"
```

### 5. Run the unified digest

```powershell
python scripts\run_browser_social_digest.py --hours 24
```

The runner writes timestamped files under `output/`:

- `browser_social_digest_*h_*.md`
- `browser_social_digest_*h_*.json`
- per-source snapshots for `X` and `WeChat`

## X Workflow

The `X` collector:

- reads enabled accounts from `sources/x_accounts.csv`
- opens a search URL per account using `from:username since:... until:...`
- waits and scrolls in a more human-like rhythm
- extracts text, timestamps, links, and engagement signals
- writes sorted JSON and Markdown summaries

Useful environment variables:

```powershell
$env:X_WINDOW_HOURS = "24"
$env:X_ACCOUNT_OFFSET = "0"
$env:X_ACCOUNT_LIMIT = "20"
$env:X_RESET_OUTPUT = "1"
```

This makes chunked runs possible when `X` gets unstable.

## WeChat Workflow

The `WeChat` collector expects a Newrank candidate file, by default:

```text
output/wechat_48h_browser_scan_v3.json
```

For each candidate article it:

1. opens the Newrank account detail page
2. clicks the left-side article card
3. reads the right-side detail panel
4. clicks the large title in the right panel
5. opens the original `mp.weixin.qq.com` article
6. extracts the article body and metadata

Required environment variable:

```powershell
$env:WECHAT_NEWRANK_TOKEN = "your_newrank_token"
```

Optional overrides:

```powershell
$env:WECHAT_WINDOW_HOURS = "24"
$env:WECHAT_SCAN_FILE = "D:\path\to\wechat_scan.json"
```

## Codex Skill

This repo includes a reusable Codex skill:

- [`skills/browser-social-digest/SKILL.md`](./skills/browser-social-digest/SKILL.md)

Use it when you want Codex to:

- reuse the browser session
- scrape recent `X` and `WeChat` updates
- write a structured digest instead of raw notes

## OpenClaw / OpenCode Integration

Prompt templates for `OpenClaw` and `OpenCode` live here:

- [`docs/openclaw-opencode-prompt-templates.md`](./docs/openclaw-opencode-prompt-templates.md)

The short version:

- do not ask those agents to “understand the whole repo” first
- tell them exactly which script to run
- tell them where the browser session lives
- tell them where to write outputs

## Privacy and Safety

This public repo intentionally does **not** include:

- your real `X` watchlist
- your real `WeChat` watchlist
- local browser profiles
- cookies, access tokens, or session dumps
- generated `output/` artifacts

Only example watchlists and template configs are committed.

## Known Limitations

- `X` can still throw blank or error states under heavier browsing pressure
- Newrank may enforce daily access limits
- `WeChat` is not yet fully end-to-end from keyword search to candidate generation in one script
- some logic still reflects a Windows-first workflow

## Suggested Next Steps

- add a dedicated Newrank scanning script from `sources/wechat_accounts.csv`
- wrap the unified runner behind a small local API or MCP server
- normalize more classifiers and summaries for public use
- add Linux/macOS browser-launch helpers

## License

No license has been added yet. If you want broader reuse, add one before inviting outside contributions.
