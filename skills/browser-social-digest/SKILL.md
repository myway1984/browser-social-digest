---
name: browser-social-digest
description: Use this skill when you need to scrape X and WeChat public accounts through a logged-in desktop Chrome session, then produce a structured digest from the captured content.
---

# Browser Social Digest

Use this skill for browser-driven monitoring workflows that combine:

- `X` account pool scraping through the X search page
- `微信公众号` article scraping through `newrank.cn`
- structured Markdown or JSON digest output

## When to use it

Trigger this skill when the user asks to:

- monitor a watchlist of `X` accounts over the past `N` hours
- monitor followed `微信公众号` via `新榜`
- produce a structured text brief from the browser session
- reuse an existing logged-in Chrome profile instead of API-only scraping

## Preconditions

- A desktop Chrome session is available and logged in to `X` and `新榜`
- Chrome is exposed over remote debugging, typically `http://127.0.0.1:9222`
- Watchlists exist as:
  - `sources/x_accounts.csv`
  - `sources/wechat_accounts.csv`
- If the real watchlists are absent, copy from:
  - `sources/x_accounts.example.csv`
  - `sources/wechat_accounts.example.csv`

## Core workflow

1. Confirm the browser is controllable over CDP and keep the current login state.
2. Run the unified pipeline:

```powershell
python scripts/run_browser_social_digest.py --hours 24
```

3. Read the generated Markdown digest under `output/`.
4. If the user wants a tighter brief, compress the generated highlights instead of re-scraping immediately.

## Key scripts

- `scripts/run_browser_social_digest.py`
  - unified entrypoint for X + WeChat + structured digest output
- `scripts/collect_x_48h_from_browser.py`
  - browser-driven X collector with human-like delays and chunking support
- `scripts/collect_wechat_48h_from_newrank.py`
  - Newrank article collector that clicks the right-side title to open the original WeChat article

## Important runtime rules

- Do not clear cookies or reset the browser profile unless the user explicitly asks.
- Prefer slower, human-like browsing rhythms on X to reduce black screens and rate limits.
- If X becomes unstable, retry with chunking:

```powershell
$env:X_ACCOUNT_OFFSET='0'
$env:X_ACCOUNT_LIMIT='20'
python scripts/collect_x_48h_from_browser.py
```

- For WeChat on Newrank, the correct reading path is:
  - open account detail page
  - click the left article card
  - inspect the right detail panel
  - click the large title in the right panel
  - read the original `mp.weixin.qq.com` article

## Known limits

- Newrank may hit daily visit caps; report partial completion instead of fabricating coverage.
- The WeChat collector expects a scanned candidate list file, by default `output/wechat_48h_browser_scan_v3.json`.
- If the candidate file is missing, report the blocker clearly and continue with X-only output if needed.

## Output files

The unified runner writes timestamped files under `output/`:

- `browser_social_digest_*h_*.md`
- `browser_social_digest_*h_*.json`
- per-source snapshots for X and WeChat

Use the Markdown digest as the user-facing default.
