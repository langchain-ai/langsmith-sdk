"""Tests for OAuth authorization server discovery in profile token refresh."""

from __future__ import annotations

from typing import Any, Callable, Optional
from unittest import mock

import pytest
import requests

from langsmith._internal._profiles import _resolve_token_endpoint

BASE = "https://deployment.example.com"
WELL_KNOWN = "/.well-known/oauth-authorization-server"


def _response(status: int, payload: Optional[Any], *, json_error: bool = False):
    response = mock.Mock()
    response.status_code = status
    if json_error:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = payload
    return response


def _patch_get(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[str], Any]
) -> list[str]:
    """Route requests.get through handler, recording the URLs probed."""
    seen: list[str] = []

    def fake_get(url: str, **_: object) -> Any:
        seen.append(url)
        return handler(url)

    monkeypatch.setattr(requests, "get", fake_get)
    return seen


def _metadata(issuer: str, token_endpoint: str) -> dict[str, str]:
    return {
        "issuer": issuer,
        "device_authorization_endpoint": f"{issuer}/oauth/device/code",
        "token_endpoint": token_endpoint,
    }


def _self_hosted(url: str) -> Any:
    """Metadata under /api, and an HTML 200 at the root like the SPA."""
    if url == f"{BASE}/api{WELL_KNOWN}":
        return _response(200, _metadata(f"{BASE}/api", f"{BASE}/api/oauth/token"))
    if url == f"{BASE}{WELL_KNOWN}":
        return _response(200, None, json_error=True)
    return _response(404, None, json_error=True)


def test_self_hosted_bare_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, _self_hosted)
    assert _resolve_token_endpoint(BASE) == f"{BASE}/api/oauth/token"


def test_self_hosted_api_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, _self_hosted)
    assert _resolve_token_endpoint(f"{BASE}/api") == f"{BASE}/api/oauth/token"


def test_saas_at_root(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str) -> Any:
        if url == f"{BASE}{WELL_KNOWN}":
            return _response(200, _metadata(BASE, f"{BASE}/oauth/token"))
        return _response(404, None, json_error=True)

    _patch_get(monkeypatch, handler)
    assert _resolve_token_endpoint(BASE) == f"{BASE}/oauth/token"


def test_saas_probes_the_origin_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare origin resolves in one request; no wasted /api probe."""

    def handler(url: str) -> Any:
        if url == f"{BASE}{WELL_KNOWN}":
            return _response(200, _metadata(BASE, f"{BASE}/oauth/token"))
        return _response(404, None, json_error=True)

    seen = _patch_get(monkeypatch, handler)
    _resolve_token_endpoint(BASE)
    assert seen == [f"{BASE}{WELL_KNOWN}"]


def test_rfc8414_path_inserted_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """RFC 8414 inserts the well-known segment before the issuer path.

    A deployment serving only that form must still be discovered.
    """

    def handler(url: str) -> Any:
        if url == f"{BASE}{WELL_KNOWN}/api":
            return _response(200, _metadata(f"{BASE}/api", f"{BASE}/api/oauth/token"))
        return _response(404, None, json_error=True)

    _patch_get(monkeypatch, handler)
    assert _resolve_token_endpoint(BASE) == f"{BASE}/api/oauth/token"


def test_bare_origin_probes_each_url_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """For a path-less issuer both forms are identical, so probe it once."""
    seen = _patch_get(monkeypatch, lambda _: _response(404, None, json_error=True))
    _resolve_token_endpoint(BASE)
    assert seen.count(f"{BASE}{WELL_KNOWN}") == 1


def test_fallback_keeps_api_mount(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without metadata the /api mount must survive; the AS lives under it."""
    _patch_get(monkeypatch, lambda _: _response(404, None, json_error=True))
    assert _resolve_token_endpoint(f"{BASE}/api") == f"{BASE}/api/oauth/token"


def test_fallback_strips_api_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, lambda _: _response(404, None, json_error=True))
    assert _resolve_token_endpoint(f"{BASE}/api/v1") == f"{BASE}/oauth/token"


def test_fallback_when_discovery_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discovery is best effort; a transport failure must not break refresh."""

    def boom(url: str, **_: object) -> Any:
        raise RuntimeError("network disabled")

    monkeypatch.setattr(requests, "get", boom)
    assert _resolve_token_endpoint(f"{BASE}/api") == f"{BASE}/api/oauth/token"


def test_rejects_issuer_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh tokens are posted here, so a foreign issuer must be ignored."""

    def handler(url: str) -> Any:
        if url == f"{BASE}{WELL_KNOWN}":
            return _response(
                200,
                _metadata("https://evil.example.com", f"{BASE}/oauth/token"),
            )
        return _response(404, None, json_error=True)

    _patch_get(monkeypatch, handler)
    assert _resolve_token_endpoint(BASE) == f"{BASE}/oauth/token"


def test_rejects_off_origin_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(url: str) -> Any:
        if url == f"{BASE}{WELL_KNOWN}":
            return _response(
                200, _metadata(BASE, "https://evil.example.com/oauth/token")
            )
        return _response(404, None, json_error=True)

    _patch_get(monkeypatch, handler)
    assert _resolve_token_endpoint(BASE) == f"{BASE}/oauth/token"
