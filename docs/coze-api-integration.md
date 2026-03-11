# Coze API Integration

This document shows the simplest way to use this repo from `Coze`.

The recommended path is:

1. run this repo locally on a machine that already has the logged-in browser session
2. expose a small local HTTP API
3. configure that API as a tool inside `Coze`

## Why This Pattern Works

`Coze` does not natively understand Codex skills or local repository workflows.

What `Coze` does handle well is:

- calling HTTP tools
- passing structured JSON
- reading a structured response

So the safest bridge is:

```text
Coze -> HTTP API -> existing Python scripts -> output files
```

## 1. Install Dependencies

From the repository root:

```powershell
python -m pip install -e .[browser,api]
python -m playwright install chromium
```

## 2. Prepare the Runtime

Before starting the API:

- Chrome is logged in to `X`
- Chrome is logged in to `newrank.cn`
- remote debugging is reachable at `http://127.0.0.1:9222`
- `WECHAT_NEWRANK_TOKEN` is set
- your real watchlists exist locally:
  - `sources/x_accounts.csv`
  - `sources/wechat_accounts.csv`

Example:

```powershell
$env:WECHAT_NEWRANK_TOKEN = "your_newrank_token"
```

## 3. Start the API Service

```powershell
python scripts\serve_digest_api.py
```

The default local address is:

```text
http://127.0.0.1:8787
```

## 4. Available Endpoints

### `GET /health`

Use this for connectivity checks.

Example response:

```json
{
  "ok": true,
  "service": "browser-social-digest-api",
  "time": "2026-03-11T16:30:00+08:00"
}
```

### `POST /digest/full`

Runs the unified digest pipeline.

Example request:

```json
{
  "hours": 24,
  "output_prefix": "coze_digest"
}
```

Example response:

```json
{
  "ok": true,
  "kind": "full",
  "hours": 24,
  "output_prefix": "coze_digest",
  "artifacts": [
    "D:\\ai_pr2\\x-grap-v1\\output\\coze_digest_24h_20260311_163000.md",
    "D:\\ai_pr2\\x-grap-v1\\output\\coze_digest_24h_20260311_163000.json"
  ],
  "stdout": "{\"digest_json\":\"...\",\"digest_md\":\"...\",\"x_posts\":42,\"wechat_articles\":5}"
}
```

### `POST /digest/x`

Runs only the `X` collector.

Example request:

```json
{
  "hours": 24,
  "output_prefix": "coze_x_digest"
}
```

### `POST /digest/wechat`

Runs only the `WeChat` collector.

Example request:

```json
{
  "hours": 24,
  "output_prefix": "coze_wechat_digest",
  "scan_file": "D:\\ai_pr2\\x-grap-v1\\output\\wechat_48h_browser_scan_v3.json"
}
```

## 5. How to Configure This in Coze

Inside `Coze`, create a custom API tool:

- Base URL: `http://127.0.0.1:8787`
- Method:
  - `GET` for `/health`
  - `POST` for `/digest/full`, `/digest/x`, `/digest/wechat`
- Content-Type: `application/json`

Recommended tool definitions:

- `run_full_social_digest`
  - path: `/digest/full`
- `run_x_digest`
  - path: `/digest/x`
- `run_wechat_digest`
  - path: `/digest/wechat`

## 6. Recommended Coze Prompting

Tell the Coze bot something like:

```text
When the user asks for a recent X or WeChat digest, call the browser-social-digest API tool first.

If the request mentions both X and WeChat, use /digest/full.
If the request only mentions X, use /digest/x.
If the request only mentions WeChat, use /digest/wechat.

After the tool returns:
- summarize the results for the user
- mention the generated artifact paths when useful
- if the tool reports partial coverage or blockers, state that clearly
```

## 7. Practical Notes

- This service is intended for local or trusted-network use.
- It is not hardened for public internet exposure.
- The browser session and token state remain on the machine that runs the service.
- `Coze` should call the API; it should not try to reproduce the browser workflow itself.

## 8. Next Upgrade Path

If you outgrow the minimal API:

- add authentication
- store runs in a proper database
- expose artifact contents directly instead of only file paths
- convert the same interface into an MCP server
