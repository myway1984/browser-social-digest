# Commit Checklist

## Ready to commit

- `.gitignore`
- `README.md`
- `config.example.toml`
- `config.verify.toml`
- `pyproject.toml`
- `docs/openclaw-opencode-prompt-templates.md`
- `scripts/collect_x_48h_from_browser.py`
- `scripts/collect_wechat_48h_from_newrank.py`
- `scripts/run_browser_social_digest.py`
- `skills/browser-social-digest/SKILL.md`
- `skills/browser-social-digest/agents/openai.yaml`
- `sources/x_accounts.example.csv`
- `sources/wechat_accounts.example.csv`
- `src/social_digest/*.py`
- `src/social_digest/fetchers/*.py`
- `COMMIT_CHECKLIST.md`

## Do not commit

- `sources/x_accounts.csv`
- `sources/wechat_accounts.csv`
- `config.toml`
- `output/`
- `runtime/`
- `data/`
- `newrank_fetches/`
- `wechat_fetches/`
- `verify_*`
- `*.html`
- `*.json`
- `*.txt`
- `gcm-diagnose.log`
- `__pycache__/`
- `*.egg-info/`

## Privacy check passed

- No hard-coded personal Windows username paths remain in shareable source files.
- No hard-coded Newrank session token remains in shareable source files.
- Personal watchlists are ignored and replaced with example CSV files.
- Local runtime outputs, browser dumps, and cached artifacts are ignored.

## Before first commit

```powershell
git status --ignored --short
git add .gitignore README.md config.example.toml config.verify.toml pyproject.toml COMMIT_CHECKLIST.md scripts skills sources/*.example.csv src
git diff --cached --stat
```

## Optional quick validation

```powershell
@'
import py_compile
files = [
    r'D:\ai_pr2\x-grap-v1\scripts\collect_x_48h_from_browser.py',
    r'D:\ai_pr2\x-grap-v1\scripts\collect_wechat_48h_from_newrank.py',
    r'D:\ai_pr2\x-grap-v1\scripts\run_browser_social_digest.py',
    r'D:\ai_pr2\x-grap-v1\src\social_digest\web_capture.py',
]
for path in files:
    py_compile.compile(path, doraise=True)
    print("OK", path)
'@ | python -
```

## Push blocker

- `git remote -v` is currently empty, so the repo is not yet connected to a GitHub remote.
