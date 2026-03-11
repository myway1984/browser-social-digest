from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output"
TZ = ZoneInfo("Asia/Shanghai")

RUNNER = ROOT / "scripts" / "run_browser_social_digest.py"
X_RUNNER = ROOT / "scripts" / "collect_x_48h_from_browser.py"
WECHAT_RUNNER = ROOT / "scripts" / "collect_wechat_48h_from_newrank.py"


class DigestRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=168)
    output_prefix: str = Field(default="browser_social_digest_api")
    wechat_scan_file: str | None = None


class SourceRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=168)
    output_prefix: str = Field(default="browser_social_digest_api")
    scan_file: str | None = None


class CommandResult(BaseModel):
    ok: bool
    command: list[str]
    stdout: str
    stderr: str
    returncode: int


app = FastAPI(
    title="Browser Social Digest API",
    version="0.1.0",
    description="Minimal HTTP wrapper for the browser-based X and WeChat digest workflow.",
)


def run_command(command: list[str], extra_env: dict[str, str] | None = None) -> CommandResult:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    return CommandResult(
        ok=result.returncode == 0,
        command=command,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def latest_outputs(prefix: str) -> list[str]:
    if not OUTPUT_DIR.exists():
        return []
    items = sorted(OUTPUT_DIR.glob(f"{prefix}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(item) for item in items[:8]]


def fail_if_needed(result: CommandResult, source: Literal["full", "x", "wechat"]) -> None:
    if result.ok:
        return
    raise HTTPException(
        status_code=500,
        detail={
            "source": source,
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
            "stdout": result.stdout.strip(),
        },
    )


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "browser-social-digest-api",
        "time": datetime.now(TZ).isoformat(),
    }


@app.post("/digest/full")
def run_full_digest(request: DigestRequest) -> dict:
    command = [sys.executable, str(RUNNER), "--hours", str(request.hours), "--output-prefix", request.output_prefix]
    if request.wechat_scan_file:
        command.extend(["--wechat-scan-file", request.wechat_scan_file])
    result = run_command(command)
    fail_if_needed(result, "full")
    return {
        "ok": True,
        "kind": "full",
        "hours": request.hours,
        "output_prefix": request.output_prefix,
        "artifacts": latest_outputs(request.output_prefix),
        "stdout": result.stdout.strip(),
    }


@app.post("/digest/x")
def run_x_digest(request: SourceRequest) -> dict:
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    prefix = f"{request.output_prefix}_x_{request.hours}h_{stamp}"
    json_path = OUTPUT_DIR / f"{prefix}.json"
    md_path = OUTPUT_DIR / f"{prefix}.md"
    env = {
        "X_WINDOW_HOURS": str(request.hours),
        "X_RESULT_FILE": str(json_path),
        "X_REPORT_FILE": str(md_path),
        "X_RESET_OUTPUT": "1",
    }
    result = run_command([sys.executable, str(X_RUNNER)], env)
    fail_if_needed(result, "x")
    return {
        "ok": True,
        "kind": "x",
        "hours": request.hours,
        "artifacts": [str(json_path), str(md_path)],
        "stdout": result.stdout.strip(),
    }


@app.post("/digest/wechat")
def run_wechat_digest(request: SourceRequest) -> dict:
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    prefix = f"{request.output_prefix}_wechat_{request.hours}h_{stamp}"
    json_path = OUTPUT_DIR / f"{prefix}.json"
    md_path = OUTPUT_DIR / f"{prefix}.md"
    env = {
        "WECHAT_WINDOW_HOURS": str(request.hours),
        "WECHAT_RESULT_FILE": str(json_path),
        "WECHAT_REPORT_FILE": str(md_path),
    }
    if request.scan_file:
        env["WECHAT_SCAN_FILE"] = request.scan_file
    result = run_command([sys.executable, str(WECHAT_RUNNER)], env)
    fail_if_needed(result, "wechat")
    return {
        "ok": True,
        "kind": "wechat",
        "hours": request.hours,
        "artifacts": [str(json_path), str(md_path)],
        "stdout": result.stdout.strip(),
    }
