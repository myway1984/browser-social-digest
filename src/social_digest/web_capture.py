from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
import os
from pathlib import Path


def _codex_home() -> Path:
    return Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))


FETCH_PAGE_SCRIPT = _codex_home() / "skills" / "anti-crawl-web-access" / "scripts" / "fetch_page.py"
EXTRACT_WECHAT_SCRIPT = _codex_home() / "skills" / "anti-crawl-web-access" / "scripts" / "extract_wechat_content.py"

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

BLOCK_PATTERNS = [
    "access denied",
    "just a moment",
    "verify you are human",
    "captcha",
    "forbidden",
    "robot",
    "security check",
    "safety verification",
    "login to continue",
    "sign in to x",
    "\u767b\u5f55\u540e\u7ee7\u7eed",
    "\u5b89\u5168\u9a8c\u8bc1",
    "\u9a8c\u8bc1\u7801",
]

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(Path(os.getenv("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe")
    if os.getenv("LOCALAPPDATA")
    else "",
    "chrome",
]

FINAL_FAILURE_NOTE = (
    "\u5df2\u4f9d\u6b21\u5c1d\u8bd5 curl \u79fb\u52a8\u7aef UA\u3001"
    "Headless dump-dom\u3001Remote Debugging\uff0c\u4ecd\u672a\u83b7\u53d6\u6b63\u6587"
)


@dataclass(slots=True)
class WebCaptureResult:
    ok: bool
    method: str
    html: str
    html_path: Path | None
    body_html: str | None
    body_path: Path | None
    note: str


class WebCapturePipeline:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.cwd()

    def capture(
        self,
        url: str,
        slug: str,
        expected_markers: list[str],
        remote_profile_dir: str | None = None,
        debug_port: int = 9222,
    ) -> WebCaptureResult:
        work_dir = (self.base_dir / "runtime" / "web_capture" / slug).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

        step1_path = work_dir / "page.html"
        self._run(
            [
                "python",
                str(FETCH_PAGE_SCRIPT),
                url,
                "--output",
                str(step1_path),
            ]
        )
        result = self._inspect_saved_output(url, step1_path, expected_markers, "curl mobile UA")
        if result.ok:
            return result

        chrome_path = self._resolve_chrome()
        if chrome_path:
            step2_path = work_dir / "page.dump_dom.html"
            html = self._dump_dom(url, chrome_path)
            step2_path.write_text(html, encoding="utf-8")
            result = self._inspect_saved_output(url, step2_path, expected_markers, "Headless dump-dom")
            if result.ok:
                return result

            result = self._capture_via_remote_debugging(
                url,
                work_dir,
                expected_markers,
                chrome_path,
                remote_profile_dir,
                debug_port,
            )
            if result.ok:
                return result

        return WebCaptureResult(
            ok=False,
            method="failed",
            html="",
            html_path=None,
            body_html=None,
            body_path=None,
            note=FINAL_FAILURE_NOTE,
        )

    def _inspect_saved_output(
        self,
        url: str,
        html_path: Path,
        expected_markers: list[str],
        method: str,
    ) -> WebCaptureResult:
        if not html_path.exists():
            return WebCaptureResult(False, method, "", None, None, None, "no html output")

        html = html_path.read_text(encoding="utf-8", errors="ignore")
        body_html, body_path = self._extract_body_if_needed(url, html_path)
        effective_html = body_html or html
        ok, note = self._looks_like_target_body(url, effective_html, expected_markers)
        return WebCaptureResult(ok, method, html, html_path, body_html, body_path, note)

    def _extract_body_if_needed(self, url: str, html_path: Path) -> tuple[str | None, Path | None]:
        if "mp.weixin.qq.com" not in url:
            return None, None
        fragment_path = html_path.with_suffix(".js_content.html")
        self._run(
            [
                "python",
                str(EXTRACT_WECHAT_SCRIPT),
                str(html_path),
                str(fragment_path),
            ]
        )
        if not fragment_path.exists():
            return None, None
        fragment = fragment_path.read_text(encoding="utf-8", errors="ignore")
        if not fragment.strip():
            return None, None
        return fragment, fragment_path

    def _dump_dom(self, url: str, chrome_path: str) -> str:
        result = subprocess.run(
            [
                chrome_path,
                "--headless=new",
                "--disable-gpu",
                f"--user-agent={MOBILE_UA}",
                "--lang=zh-CN",
                "--virtual-time-budget=15000",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        return result.stdout or ""

    def _capture_via_remote_debugging(
        self,
        url: str,
        work_dir: Path,
        expected_markers: list[str],
        chrome_path: str,
        remote_profile_dir: str | None,
        debug_port: int,
    ) -> WebCaptureResult:
        profile_dir = (
            (self.base_dir / remote_profile_dir).resolve()
            if remote_profile_dir
            else (Path(tempfile.gettempdir()) / f"social-digest-remote-debug-{debug_port}")
        )
        profile_dir.mkdir(parents=True, exist_ok=True)

        subprocess.Popen(
            [
                chrome_path,
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={profile_dir}",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        time.sleep(4)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return WebCaptureResult(False, "Remote Debugging", "", None, None, None, "playwright unavailable")

        final_path = work_dir / "page.remote_debug.html"
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            html = page.content()
            final_path.write_text(html, encoding="utf-8")
            browser.close()

        return self._inspect_saved_output(url, final_path, expected_markers, "Remote Debugging")

    def _looks_like_target_body(self, url: str, html: str, expected_markers: list[str]) -> tuple[bool, str]:
        if not html.strip():
            return False, "empty html"

        lowered = html.lower()
        if any(pattern in lowered for pattern in BLOCK_PATTERNS):
            return False, "blocked or verification page"

        if "mp.weixin.qq.com" in url:
            if 'id="js_content"' in lowered or "id='js_content'" in lowered:
                return True, "found js_content"
            return False, "wechat body missing"

        if expected_markers and not any(marker.lower() in lowered for marker in expected_markers):
            return False, "target body missing"

        if len(html) < 200:
            return False, "html too small"
        return True, "body found"

    def _resolve_chrome(self) -> str | None:
        for candidate in CHROME_CANDIDATES:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists():
                return str(path)
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def _run(self, command: list[str]) -> None:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
