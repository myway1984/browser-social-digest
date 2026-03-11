# OpenClaw / OpenCode Prompt Templates

These templates help you reuse this repo from another agent framework without requiring native Codex skill support.

The most reliable pattern is:

1. give the agent a narrow task
2. point it to one script
3. tell it where the browser session lives
4. tell it where outputs should be written

## Before You Use These Templates

Make sure the runtime is already prepared:

- Chrome is logged in to `X`
- Chrome is logged in to `newrank.cn`
- remote debugging is available at `http://127.0.0.1:9222`
- `WECHAT_NEWRANK_TOKEN` is set
- watchlists exist in:
  - `sources/x_accounts.csv`
  - `sources/wechat_accounts.csv`

## Template 1: Full Digest

Use this when you want the agent to run the whole pipeline and return a structured brief.

```text
You are operating inside the repository browser-social-digest.

Goal:
Run the browser-based social digest workflow for the last 24 hours and return a structured summary.

Constraints:
- Reuse the existing logged-in Chrome session.
- Do not clear cookies, reset the browser profile, or log out of any site.
- Prefer the unified runner instead of reimplementing the workflow.
- If X becomes unstable, switch to smaller chunked runs rather than abandoning the task.
- If WeChat candidate data is missing, report that blocker clearly and continue with X-only output.

Primary command:
python scripts/run_browser_social_digest.py --hours 24

Expected output:
- Read the generated Markdown digest under output/.
- Summarize the most important themes, top accounts, and any blockers.
- Mention the exact digest file path in the final response.
```

## Template 2: X Only

Use this when you only want `X` updates from the watchlist.

```text
You are operating inside the repository browser-social-digest.

Goal:
Collect the last 24 hours of X updates from the configured watchlist and summarize the most important content.

Constraints:
- Reuse the existing logged-in Chrome session at the current CDP endpoint.
- Use the existing browser collector script rather than building a new scraper.
- Use slower, more human-like browsing behavior if the platform becomes unstable.
- Keep the output structured by theme, account, timestamp, and link.

Command:
python scripts/collect_x_48h_from_browser.py

Environment assumptions:
- X_WINDOW_HOURS=24
- X_RESET_OUTPUT=1

Expected output:
- Read the generated JSON/Markdown output.
- Return a concise structured brief with:
  - top themes
  - top posts
  - notable accounts
  - any collection errors
```

## Template 3: WeChat Only

Use this when you only want `WeChat` article extraction from Newrank candidates.

```text
You are operating inside the repository browser-social-digest.

Goal:
Collect recent WeChat public account articles from the Newrank candidate list and summarize them.

Constraints:
- Reuse the existing logged-in Chrome session.
- Use the existing WeChat collector script.
- On each article:
  1. click the left article card
  2. read the right-side detail panel
  3. click the large title in the right panel
  4. extract the original WeChat article
- Do not stop at the Newrank summary panel.
- If Newrank access limits block progress, report partial completion instead of fabricating results.

Command:
python scripts/collect_wechat_48h_from_newrank.py

Environment assumptions:
- WECHAT_WINDOW_HOURS=24
- WECHAT_NEWRANK_TOKEN is already set
- WECHAT_SCAN_FILE points to a valid candidate file if the default file is absent

Expected output:
- Read the generated JSON/Markdown output.
- Return a structured brief with:
  - matched articles
  - account names
  - publish times
  - panel summary
  - original article links
  - blockers or access-limit issues
```

## Template 4: Safer Tool-Use Version

Use this when the external agent tends to over-explore or rewrite workflows.

```text
Work only with the scripts already present in this repository.

Do not redesign the data model.
Do not replace browser automation with public web scraping unless the existing script explicitly fails.
Do not delete browser state, cookies, or profile data.
Do not commit or push any code changes unless explicitly asked.

Preferred order:
1. inspect the target script
2. run the target script
3. read the generated output file
4. summarize findings
5. only patch code if the task explicitly requires a fix
```

## Recommended Wrapping Pattern

If you want stronger portability across agent systems:

- keep this repo as the implementation layer
- expose `scripts/run_browser_social_digest.py` through a tiny local API or MCP tool
- have `OpenClaw` or `OpenCode` call that API instead of directly reinterpreting repository logic

That is usually more stable than relying on a long free-form prompt alone.
