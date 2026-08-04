"""Tests for OAuth authorization server discovery in profile token refresh."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Iterator

import pytest

from langsmith._internal._profiles import _resolve_token_endpoint


def _serve(handler_fn: Callable[[str, str], Any]) -> Iterator[str]:
    """Run an HTTP server whose handler maps (path, base_url) to a response.

    handler_fn returns either a dict (encoded as JSON), a str (sent as HTML), or
    None for a 404.
    """
    base_holder: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            result = handler_fn(self.path, base_holder["base"])
            if result is None:
                self.send_response(404)
                self.end_headers()
                return
            if isinstance(result, dict):
                body = json.dumps(result).encode()
                content_type = "application/json"
            else:
                body = str(result).encode()
                content_type = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    base_holder["base"] = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield base_holder["base"]
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def self_hosted() -> Iterator[str]:
    """Metadata under /api, plus an HTML 200 at the root like the SPA."""

    def handler(path: str, base: str) -> Any:
        if path == "/api/.well-known/oauth-authorization-server":
            return {
                "issuer": f"{base}/api",
                "device_authorization_endpoint": f"{base}/api/oauth/device/code",
                "token_endpoint": f"{base}/api/oauth/token",
            }
        if path == "/.well-known/oauth-authorization-server":
            return "<!doctype html><html><body>app</body></html>"
        return None

    yield from _serve(handler)


@pytest.fixture
def saas() -> Iterator[str]:
    def handler(path: str, base: str) -> Any:
        if path == "/.well-known/oauth-authorization-server":
            return {
                "issuer": base,
                "device_authorization_endpoint": f"{base}/oauth/device/code",
                "token_endpoint": f"{base}/oauth/token",
            }
        return None

    yield from _serve(handler)


@pytest.fixture
def no_metadata() -> Iterator[str]:
    yield from _serve(lambda path, base: None)


def test_self_hosted_bare_origin(self_hosted: str) -> None:
    assert _resolve_token_endpoint(self_hosted) == f"{self_hosted}/api/oauth/token"


def test_self_hosted_api_suffix(self_hosted: str) -> None:
    assert (
        _resolve_token_endpoint(f"{self_hosted}/api")
        == f"{self_hosted}/api/oauth/token"
    )


def test_saas_at_root(saas: str) -> None:
    assert _resolve_token_endpoint(saas) == f"{saas}/oauth/token"


def test_fallback_keeps_api_mount(no_metadata: str) -> None:
    """Without metadata the /api mount must survive; the AS lives under it."""
    assert (
        _resolve_token_endpoint(f"{no_metadata}/api")
        == f"{no_metadata}/api/oauth/token"
    )


def test_fallback_strips_api_v1(no_metadata: str) -> None:
    assert (
        _resolve_token_endpoint(f"{no_metadata}/api/v1") == f"{no_metadata}/oauth/token"
    )


def test_rejects_issuer_mismatch() -> None:
    """Refresh tokens are posted here, so a foreign issuer must be ignored."""

    def handler(path: str, base: str) -> Any:
        if path == "/.well-known/oauth-authorization-server":
            return {
                "issuer": "https://evil.example.com",
                "device_authorization_endpoint": f"{base}/oauth/device/code",
                "token_endpoint": f"{base}/oauth/token",
            }
        return None

    for base in _serve(handler):
        assert _resolve_token_endpoint(base) == f"{base}/oauth/token"


def test_rejects_off_origin_endpoint() -> None:
    def handler(path: str, base: str) -> Any:
        if path == "/.well-known/oauth-authorization-server":
            return {
                "issuer": base,
                "device_authorization_endpoint": f"{base}/oauth/device/code",
                "token_endpoint": "https://evil.example.com/oauth/token",
            }
        return None

    for base in _serve(handler):
        # Falls back rather than trusting the document.
        assert _resolve_token_endpoint(base) == f"{base}/oauth/token"
