#!/usr/bin/env -S uv run --with-editable . --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "playwright>=1.58.0",
#   "websockets>=15.0",
# ]
# ///
"""Run Chrome in a LangSmith sandbox and drive it with local Playwright.

This example starts a visible Chrome session inside the sandbox, exposes it
through noVNC, and connects the same browser instance to local Playwright over
Chrome DevTools Protocol (CDP).

Set LANGSMITH_API_KEY and, when needed, LANGSMITH_ENDPOINT.
"""

from __future__ import annotations

import select
import sys
import termios
import textwrap
import time
import tty
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import BrowserContext, ConsoleMessage, Page, sync_playwright

from langsmith.sandbox import SandboxClient, SandboxClientError, Snapshot

NOVNC_PORT = 6080
CDP_PORT = 9222
BROWSER_SNAPSHOT_NAME = "browser-playwright-novnc"


def log(message: str) -> None:
    """Print a progress message."""
    print(message, flush=True)  # noqa: T201


@contextmanager
def raw_terminal() -> Iterator[None]:
    """Temporarily read single keys from stdin without requiring Enter."""
    if not sys.stdin.isatty():
        yield
        return

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin)
        yield
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def read_key() -> str | None:
    """Return one pending terminal key, if any."""
    if not sys.stdin.isatty():
        return None
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if not readable:
        return None
    return sys.stdin.read(1)


def novnc_viewer_url(browser_url: str) -> str:
    """Return an authenticated noVNC viewer URL for a sandbox service URL."""
    parts = urlsplit(browser_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["path"] = "vnc.html"
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query and urlencode(query), "")
    )


CLICK_LISTENER_SCRIPT = """
(() => {
  if (window.__langsmithSandboxClickLoggerInstalled) return;
  window.__langsmithSandboxClickLoggerInstalled = true;

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const label = (
      target.innerText ||
      target.getAttribute("aria-label") ||
      target.getAttribute("title") ||
      target.getAttribute("href") ||
      ""
    ).trim().replace(/\\s+/g, " ").slice(0, 120);

    const detail = {
      tag: target.tagName.toLowerCase(),
      id: target.id || "",
      classes: Array.from(target.classList || []).slice(0, 4).join("."),
      text: label,
      x: Math.round(event.clientX),
      y: Math.round(event.clientY),
      url: window.location.href,
    };

    console.log("__LANGSMITH_SANDBOX_CLICK__" + JSON.stringify(detail));
  }, true);

  document.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) &&
        !(target instanceof HTMLTextAreaElement) &&
        !(target instanceof HTMLSelectElement)) {
      return;
    }

    const detail = {
      tag: target.tagName.toLowerCase(),
      id: target.id || "",
      name: target.getAttribute("name") || "",
      type: target.getAttribute("type") || "",
      value: (target.value || "").slice(0, 120),
      url: window.location.href,
    };

    console.log("__LANGSMITH_SANDBOX_INPUT__" + JSON.stringify(detail));
  }, true);
})();
"""


def attach_page_logging(page: Page) -> None:
    """Attach navigation and click logging to a Playwright page."""

    def log_navigation(frame) -> None:  # type: ignore[no-untyped-def]
        if frame == page.main_frame:
            log(f"Navigation: {frame.url}")

    def log_console(message: ConsoleMessage) -> None:
        text = message.text
        if text.startswith("__LANGSMITH_SANDBOX_CLICK__"):
            log(f"Click: {text.removeprefix('__LANGSMITH_SANDBOX_CLICK__')}")
        if text.startswith("__LANGSMITH_SANDBOX_INPUT__"):
            log(f"Input: {text.removeprefix('__LANGSMITH_SANDBOX_INPUT__')}")

    page.on("framenavigated", log_navigation)
    page.on("console", log_console)
    page.add_init_script(CLICK_LISTENER_SCRIPT)
    try:
        page.evaluate(CLICK_LISTENER_SCRIPT)
    except Exception:
        pass


def attach_context_logging(context: BrowserContext) -> set[Page]:
    """Attach logging to current and future pages in a browser context."""
    seen: set[Page] = set()

    def attach_once(page: Page) -> None:
        if page in seen:
            return
        seen.add(page)
        attach_page_logging(page)

    for page in context.pages:
        attach_once(page)
    context.on("page", attach_once)
    return seen


def log_page_changes(context: BrowserContext, seen_urls: dict[Page, str]) -> None:
    """Poll pages for URL changes and attach listeners to newly visible pages."""
    for page in context.pages:
        url = page.url
        if seen_urls.get(page) != url:
            seen_urls[page] = url
            log(f"Navigation: {url}")


def active_page(context: BrowserContext) -> Page:
    """Return the most recently opened page, or create one."""
    return context.pages[-1] if context.pages else context.new_page()


def dump_aria_snapshot(page: Page) -> None:
    """Print the current page ARIA snapshot."""
    log("\nARIA snapshot:")
    log(page.locator("body").aria_snapshot(timeout=5000))


START_BROWSER_SCRIPT = r"""
set -euo pipefail

export DISPLAY=:99
mkdir -p /tmp/chrome-profile

if ! pgrep -x Xvfb >/dev/null; then
  Xvfb :99 -screen 0 1440x900x24 >/tmp/xvfb.log 2>&1 &
fi

for _ in $(seq 1 60); do
  if [ -S /tmp/.X11-unix/X99 ]; then
    break
  fi
  sleep 0.5
done

if [ ! -S /tmp/.X11-unix/X99 ]; then
  echo "Xvfb did not become ready. Last Xvfb log lines:" >&2
  tail -50 /tmp/xvfb.log >&2 || true
  exit 1
fi

if ! pgrep -x x11vnc >/dev/null; then
  x11vnc -display :99 -forever -shared -nopw -listen 127.0.0.1 \
    -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
fi

if ! curl -fsS http://127.0.0.1:6080/ >/dev/null 2>&1; then
  websockify --web /usr/share/novnc 0.0.0.0:6080 127.0.0.1:5900 \
    >/tmp/novnc.log 2>&1 &
fi

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:6080/ >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS http://127.0.0.1:6080/ >/dev/null 2>&1; then
  echo "noVNC did not become reachable on port 6080." >&2
  echo "Last noVNC log lines:" >&2
  tail -50 /tmp/novnc.log >&2 || true
  echo "Last x11vnc log lines:" >&2
  tail -50 /tmp/x11vnc.log >&2 || true
  exit 1
fi

if command -v google-chrome >/dev/null 2>&1; then
  CHROME=google-chrome
elif command -v chromium >/dev/null 2>&1; then
  CHROME=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
  CHROME=chromium-browser
else
  echo "Chrome/Chromium is not installed." >&2
  exit 1
fi

if ! curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
  "$CHROME" \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --window-size=1440,900 \
    --user-data-dir=/tmp/chrome-profile \
    --remote-debugging-address=0.0.0.0 \
    --remote-debugging-port=9222 \
    about:blank >/tmp/chrome.log 2>&1 &
fi

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
    echo "Chrome is ready on CDP port 9222; noVNC is on port 6080."
    exit 0
  fi
  sleep 0.5
done

echo "Chrome did not become ready. Last chrome log lines:" >&2
tail -50 /tmp/chrome.log >&2 || true
exit 1
"""


SNAPSHOT_INIT_SCRIPT = r"""
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  novnc \
  wget \
  websockify \
  x11vnc \
  xvfb

wget -qO- https://dl.google.com/linux/linux_signing_key.pub \
  | gpg --dearmor >/usr/share/keyrings/google-linux-signing-keyring.gpg
printf '%s %s %s\n' \
  'deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg]' \
  'http://dl.google.com/linux/chrome/deb/' \
  'stable main' >/etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y --no-install-recommends google-chrome-stable

rm -rf /var/lib/apt/lists/*
"""


def _find_snapshot(client: SandboxClient, name: str) -> Snapshot | None:
    for snapshot in client.list_snapshots(name_contains=name, limit=100):
        if snapshot.name == name:
            return snapshot
    return None


def ensure_browser_snapshot(client: SandboxClient) -> Snapshot:
    """Return a browser snapshot, creating it from a prepared sandbox if needed."""
    log(f"Looking for snapshot {BROWSER_SNAPSHOT_NAME!r}.")
    existing = _find_snapshot(client, BROWSER_SNAPSHOT_NAME)
    if existing is not None:
        log(f"Reusing snapshot {existing.name!r} ({existing.id}); waiting for ready.")
        return client.wait_for_snapshot(existing.id, timeout=600)

    log("Snapshot not found. Creating setup sandbox without a snapshot.")
    setup_sandbox = client.create_sandbox()
    try:
        log(f"Installing browser dependencies in setup sandbox {setup_sandbox.name!r}.")
        result = setup_sandbox.run(
            textwrap.dedent(SNAPSHOT_INIT_SCRIPT),
            timeout=600,
        )
        if not result.success:
            raise RuntimeError(result.stderr or result.stdout)
        try:
            log(f"Capturing setup sandbox as snapshot {BROWSER_SNAPSHOT_NAME!r}.")
            return client.capture_snapshot(
                setup_sandbox.name,
                BROWSER_SNAPSHOT_NAME,
                timeout=600,
            )
        except SandboxClientError as exc:
            if "already exists" not in str(exc):
                raise
            log("Snapshot was created concurrently; waiting for the existing one.")
            existing = _find_snapshot(client, BROWSER_SNAPSHOT_NAME)
            if existing is None:
                raise
            return client.wait_for_snapshot(existing.id, timeout=600)
    finally:
        log(f"Deleting setup sandbox {setup_sandbox.name!r}.")
        setup_sandbox.delete()


def main() -> None:
    """Start Chrome in a sandbox and control it through CDP."""
    client = SandboxClient()
    snapshot = ensure_browser_snapshot(client)

    log(f"Launching browser sandbox from snapshot {snapshot.name!r} ({snapshot.id}).")
    with client.sandbox(snapshot_id=snapshot.id) as sandbox:
        log(f"Starting Xvfb, noVNC, and Chrome in sandbox {sandbox.name!r}.")
        result = sandbox.run(
            textwrap.dedent(START_BROWSER_SCRIPT),
            timeout=90,
        )
        if not result.success:
            raise RuntimeError(result.stderr or result.stdout)

        novnc = sandbox.service(port=NOVNC_PORT, expires_in_seconds=3600)
        log(f"Open noVNC to watch the browser: {novnc_viewer_url(novnc.browser_url)}")

        log(f"Opening CDP tunnel to sandbox port {CDP_PORT}.")
        with sandbox.tunnel(remote_port=CDP_PORT, local_port=0) as cdp:
            cdp_url = f"http://127.0.0.1:{cdp.local_port}"
            log(f"Connecting local Playwright to {cdp_url}.")

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]
                pages = attach_context_logging(context)
                page = context.pages[0] if context.pages else context.new_page()
                seen_urls = {logged_page: logged_page.url for logged_page in pages}
                page.goto("https://example.com", wait_until="domcontentloaded")
                log_page_changes(context, seen_urls)
                log(f"Remote page title: {page.title()}")

                try:
                    log("Press q to quit, a to dump the ARIA snapshot.")
                    last_keepalive = 0.0
                    with raw_terminal():
                        while True:
                            key = read_key()
                            if key == "q":
                                log("\nQuitting.")
                                break
                            if key == "a":
                                dump_aria_snapshot(active_page(context))

                            for current_page in context.pages:
                                if current_page not in pages:
                                    pages.add(current_page)
                                    attach_page_logging(current_page)
                            log_page_changes(context, seen_urls)

                            now = time.monotonic()
                            if now - last_keepalive >= 10:
                                sandbox.run("true", timeout=10)
                                last_keepalive = now

                            active_page(context).wait_for_timeout(1000)
                finally:
                    log("Closing local Playwright connection.")
                    browser.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nStopped.")
