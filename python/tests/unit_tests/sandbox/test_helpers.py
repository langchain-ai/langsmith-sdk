"""Unit tests for langsmith.sandbox._helpers."""

import httpx

from langsmith.sandbox._helpers import merge_headers, parse_error_response


def test_merge_headers_override_wins() -> None:
    # Names are normalized to lowercase and the override wins.
    merged = merge_headers({"X-Service-Key": "base"}, {"X-Service-Key": "override"})
    assert merged == {"x-service-key": "override"}


def test_merge_headers_preserves_non_overridden_base() -> None:
    merged = merge_headers({"a": "1", "b": "2"}, {"b": "3"})
    assert merged == {"a": "1", "b": "3"}


def test_merge_headers_none_inputs() -> None:
    assert merge_headers(None, None) == {}
    assert merge_headers({"a": "1"}, None) == {"a": "1"}
    assert merge_headers(None, {"a": "1"}) == {"a": "1"}


def test_merge_headers_override_replaces_across_casing() -> None:
    # httpx.Headers normalizes names to lowercase; a Title-Case override must
    # still replace the base rather than produce a second, duplicate header.
    base = httpx.Headers({"X-Service-Key": "base", "X-Api-Key": ""})
    merged = merge_headers(base, {"X-Service-Key": "override"})

    assert [v for k, v in merged.items() if k.lower() == "x-service-key"] == [
        "override"
    ]
    # And only one X-Service-Key actually goes on the wire.
    request = httpx.Request("GET", "https://example.com", headers=merged)
    on_wire = [
        v.decode() for k, v in request.headers.raw if k.lower() == b"x-service-key"
    ]
    assert on_wire == ["override"]


def test_parse_error_response_preserves_error_id() -> None:
    request = httpx.Request(
        "POST", "https://example.com/v2/sandboxes/boxes/box/snapshot"
    )
    response = httpx.Response(
        500,
        request=request,
        json={
            "detail": {
                "error": "SandboxSnapshotFailed",
                "message": "Snapshot capture failed.",
                "error_id": "6a39f608-e9aa-4247-8e61-846870563681",
            }
        },
    )
    error = httpx.HTTPStatusError("server error", request=request, response=response)

    assert parse_error_response(error) == {
        "error_type": "SandboxSnapshotFailed",
        "message": (
            "Snapshot capture failed. (error_id=6a39f608-e9aa-4247-8e61-846870563681)"
        ),
    }
