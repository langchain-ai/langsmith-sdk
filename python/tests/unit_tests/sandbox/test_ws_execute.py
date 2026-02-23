"""Tests for WebSocket transport helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from langsmith.sandbox._exceptions import (
    CommandTimeoutError,
    SandboxConnectionError,
    SandboxOperationError,
)
from langsmith.sandbox._ws_execute import (
    _build_auth_headers,
    _build_ws_url,
    _raise_from_error_msg,
    _WSStreamControl,
)

# =============================================================================
# Tests: Helpers
# =============================================================================


class TestBuildWsUrl:
    def test_https_to_wss(self):
        assert _build_ws_url("https://example.com/sb-123") == (
            "wss://example.com/sb-123/execute/ws"
        )

    def test_http_to_ws(self):
        assert _build_ws_url("http://localhost:8080/sb-123") == (
            "ws://localhost:8080/sb-123/execute/ws"
        )


class TestBuildAuthHeaders:
    def test_builds_header(self):
        headers = _build_auth_headers("my-key")
        assert headers == {"X-Api-Key": "my-key"}

    def test_none_key_returns_empty(self):
        headers = _build_auth_headers(None)
        assert headers == {}


# =============================================================================
# Tests: _WSStreamControl
# =============================================================================


class TestWSStreamControl:
    def test_initial_state(self):
        ctrl = _WSStreamControl()
        assert ctrl.killed is False

    def test_bind_unbind(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        assert ctrl._ws is ws
        ctrl._unbind()
        assert ctrl._ws is None
        assert ctrl._closed is True

    def test_send_kill(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl.send_kill()
        assert ctrl.killed is True
        ws.send.assert_called_once_with(json.dumps({"type": "kill"}))

    def test_send_kill_when_closed(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl._unbind()
        ctrl.send_kill()
        assert ctrl.killed is True
        ws.send.assert_not_called()

    def test_send_input(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl.send_input("hello\n")
        ws.send.assert_called_once_with(
            json.dumps({"type": "input", "data": "hello\n"})
        )


# =============================================================================
# Tests: _raise_from_error_msg
# =============================================================================


class TestRaiseFromErrorMsg:
    def test_command_timeout(self):
        with pytest.raises(CommandTimeoutError):
            _raise_from_error_msg(
                {"type": "error", "error": "timed out", "error_type": "CommandTimeout"}
            )

    def test_command_not_found(self):
        with pytest.raises(
            SandboxOperationError, match="Command not found"
        ) as exc_info:
            _raise_from_error_msg(
                {
                    "type": "error",
                    "error": "not found",
                    "error_type": "CommandNotFound",
                },
                command_id="cmd-123",
            )
        assert exc_info.value.error_type == "CommandNotFound"
        assert exc_info.value.operation == "reconnect"

    def test_session_expired(self):
        with pytest.raises(SandboxOperationError, match="Session expired") as exc_info:
            _raise_from_error_msg(
                {"type": "error", "error": "expired", "error_type": "SessionExpired"},
                command_id="cmd-456",
            )
        assert exc_info.value.error_type == "SessionExpired"

    def test_generic_error(self):
        with pytest.raises(SandboxOperationError, match="something broke"):
            _raise_from_error_msg(
                {"type": "error", "error": "something broke", "error_type": "Unknown"}
            )

    def test_default_error_type(self):
        with pytest.raises(SandboxOperationError):
            _raise_from_error_msg({"type": "error", "error": "oops"})


# =============================================================================
# Tests: _raise_for_invalid_status
# =============================================================================


class TestRaiseForInvalidStatus:
    def test_404_gives_clear_message_with_url(self):
        from langsmith.sandbox._ws_execute import _raise_for_invalid_status

        mock_response = MagicMock()
        mock_response.status_code = 404
        exc = Exception("server rejected WebSocket connection: HTTP 404")
        exc.response = mock_response

        with pytest.raises(SandboxConnectionError) as exc_info:
            _raise_for_invalid_status(
                exc,
                "ws://example.com/sb-123/execute/ws",
            )
        msg = str(exc_info.value)
        assert "does not support WebSocket" in msg
        assert "execute/ws returned 404" in msg
        assert exc_info.value.__cause__ is exc

    def test_non_404_includes_status_code(self):
        from langsmith.sandbox._ws_execute import _raise_for_invalid_status

        mock_response = MagicMock()
        mock_response.status_code = 403
        exc = Exception("HTTP 403")
        exc.response = mock_response

        with pytest.raises(SandboxConnectionError, match="HTTP 403"):
            _raise_for_invalid_status(exc, "ws://example.com/sb-123/execute/ws")
