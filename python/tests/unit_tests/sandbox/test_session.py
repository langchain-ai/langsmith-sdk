"""Tests for interactive PTY sessions (sync)."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._session import Session, SessionInfo
from langsmith.sandbox._ws_session import (
    _SessionWSControl,
    _build_session_ws_url,
)


# =============================================================================
# Tests: _build_session_ws_url
# =============================================================================


class TestBuildSessionWsUrl:
    def test_https_to_wss(self):
        assert _build_session_ws_url("https://example.com/sb-123", "sess-1") == (
            "wss://example.com/sb-123/sessions/sess-1/ws"
        )

    def test_http_to_ws(self):
        assert _build_session_ws_url("http://localhost:8080/sb-123", "sess-2") == (
            "ws://localhost:8080/sb-123/sessions/sess-2/ws"
        )


# =============================================================================
# Tests: _SessionWSControl
# =============================================================================


class TestSessionWSControl:
    def test_initial_state(self):
        ctrl = _SessionWSControl()
        assert ctrl.connected is False

    def test_bind_unbind(self):
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        assert ctrl.connected is True
        ctrl._unbind()
        assert ctrl.connected is False

    def test_send_input_base64_encodes(self):
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl.send_input("hello\n")
        expected_b64 = base64.b64encode(b"hello\n").decode("ascii")
        ws.send.assert_called_once_with(
            json.dumps({"type": "input", "data": expected_b64})
        )

    def test_send_resize(self):
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl.send_resize(120, 40)
        ws.send.assert_called_once_with(
            json.dumps({"type": "resize", "cols": 120, "rows": 40})
        )

    def test_send_input_when_closed(self):
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl._unbind()
        ctrl.send_input("data")
        ws.send.assert_not_called()

    def test_send_resize_when_closed(self):
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        ctrl._unbind()
        ctrl.send_resize(80, 24)
        ws.send.assert_not_called()



# =============================================================================
# Tests: SessionInfo
# =============================================================================


class TestSessionInfo:
    def test_from_dict(self):
        info = SessionInfo.from_dict(
            {
                "id": "sess-1",
                "shell": "/bin/bash",
                "workdir": "/home/user",
                "created_at": "2025-01-01T00:00:00Z",
                "last_access": "2025-01-01T00:01:00Z",
            }
        )
        assert info.id == "sess-1"
        assert info.shell == "/bin/bash"
        assert info.workdir == "/home/user"
        assert info.created_at == "2025-01-01T00:00:00Z"
        assert info.last_access == "2025-01-01T00:01:00Z"

    def test_from_dict_minimal(self):
        info = SessionInfo.from_dict({"id": "sess-2"})
        assert info.id == "sess-2"
        assert info.shell == ""
        assert info.workdir == ""
        assert info.created_at is None
        assert info.last_access is None


# =============================================================================
# Helpers
# =============================================================================


def _make_sandbox_mock() -> Any:
    """Create a mock Sandbox with dataplane_url and client."""
    sandbox = MagicMock()
    sandbox._require_dataplane_url.return_value = "https://router.example.com/sb-123"
    sandbox._client._api_key = "test-key"
    sandbox._client._http = MagicMock()
    return sandbox


def _output_iter(chunks: list[str]) -> Iterator[str]:
    """Create a simple string iterator."""
    yield from chunks


# =============================================================================
# Tests: Session lifecycle
# =============================================================================


class TestSession:
    def test_properties(self):
        sandbox = _make_sandbox_mock()
        session = Session("sess-1", sandbox, shell="/bin/bash", workdir="/home")
        assert session.session_id == "sess-1"
        assert session.connected is False

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_connect_disconnect(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _SessionWSControl()
        ctrl._bind(MagicMock())  # simulate bound
        mock_connect.return_value = (_output_iter([]), ctrl)

        session = Session("sess-1", sandbox)
        session.connect()
        assert session.connected is True

        session.disconnect()
        assert session.connected is False

    def test_send_input_not_connected_raises(self):
        sandbox = _make_sandbox_mock()
        session = Session("sess-1", sandbox)
        with pytest.raises(SandboxOperationError, match="not connected"):
            session.send_input("hello")

    def test_resize_not_connected_raises(self):
        sandbox = _make_sandbox_mock()
        session = Session("sess-1", sandbox)
        with pytest.raises(SandboxOperationError, match="not connected"):
            session.resize(80, 24)

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_send_input_connected(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        mock_connect.return_value = (_output_iter([]), ctrl)

        session = Session("sess-1", sandbox)
        session.connect()
        session.send_input("ls\n")

        expected_b64 = base64.b64encode(b"ls\n").decode("ascii")
        ws.send.assert_called_once_with(
            json.dumps({"type": "input", "data": expected_b64})
        )

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_resize_connected(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _SessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        mock_connect.return_value = (_output_iter([]), ctrl)

        session = Session("sess-1", sandbox)
        session.connect()
        session.resize(120, 40)

        ws.send.assert_called_once_with(
            json.dumps({"type": "resize", "cols": 120, "rows": 40})
        )

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_iteration_yields_output(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _SessionWSControl()
        ctrl._bind(MagicMock())
        mock_connect.return_value = (_output_iter(["hello", " world"]), ctrl)

        session = Session("sess-1", sandbox)
        session.connect()
        output = list(session)
        assert output == ["hello", " world"]

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_auto_reconnect_on_connection_error(self, mock_connect):
        sandbox = _make_sandbox_mock()

        # First connect: yields data then fails
        call_count = [0]

        def make_connect(*args, **kwargs):
            call_count[0] += 1
            ctrl = _SessionWSControl()
            ctrl._bind(MagicMock())
            if call_count[0] == 1:

                def failing():
                    yield "part1"
                    raise SandboxConnectionError("lost")

                return failing(), ctrl
            else:

                def succeeding():
                    yield "part2"

                return succeeding(), ctrl

        mock_connect.side_effect = make_connect

        session = Session("sess-1", sandbox)
        session.connect()

        with patch("time.sleep") as mock_sleep:
            output = list(session)

        assert output == ["part1", "part2"]
        assert call_count[0] == 2
        mock_sleep.assert_called_once_with(0.5)

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_auto_reconnect_server_reload_no_backoff(self, mock_connect):
        sandbox = _make_sandbox_mock()
        call_count = [0]

        def make_connect(*args, **kwargs):
            call_count[0] += 1
            ctrl = _SessionWSControl()
            ctrl._bind(MagicMock())
            if call_count[0] == 1:

                def failing():
                    yield "data"
                    raise SandboxServerReloadError("reloading")

                return failing(), ctrl
            else:
                return _output_iter(["more"]), ctrl

        mock_connect.side_effect = make_connect

        session = Session("sess-1", sandbox)
        session.connect()

        with patch("time.sleep") as mock_sleep:
            output = list(session)
            mock_sleep.assert_not_called()

        assert output == ["data", "more"]

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_max_reconnects_exceeded(self, mock_connect):
        sandbox = _make_sandbox_mock()

        def make_connect(*args, **kwargs):
            ctrl = _SessionWSControl()
            ctrl._bind(MagicMock())

            def failing():
                raise SandboxConnectionError("lost")
                yield  # make it a generator  # noqa: E501

            return failing(), ctrl

        mock_connect.side_effect = make_connect

        session = Session("sess-1", sandbox)
        session.connect()

        with patch("time.sleep"):
            with pytest.raises(SandboxConnectionError, match="giving up"):
                list(session)

    def test_close_calls_http_delete(self):
        sandbox = _make_sandbox_mock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        sandbox._client._http.delete.return_value = mock_response

        session = Session("sess-1", sandbox)
        session.close()

        sandbox._client._http.delete.assert_called_once_with(
            "https://router.example.com/sb-123/sessions/sess-1",
            timeout=30,
        )

    def test_context_manager_calls_close(self):
        sandbox = _make_sandbox_mock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        sandbox._client._http.delete.return_value = mock_response

        session = Session("sess-1", sandbox)
        with session:
            pass

        sandbox._client._http.delete.assert_called_once()

    def test_context_manager_suppresses_close_errors(self):
        sandbox = _make_sandbox_mock()
        sandbox._client._http.delete.side_effect = Exception("network error")

        session = Session("sess-1", sandbox)
        with session:
            pass  # Should not raise

    @patch("langsmith.sandbox._session.connect_session_ws")
    def test_reconnect_counter_resets_on_data(self, mock_connect):
        """Successful data resets reconnect counter."""
        sandbox = _make_sandbox_mock()
        call_count = [0]
        max_reconnects = Session.MAX_AUTO_RECONNECTS + 3

        def make_connect(*args, **kwargs):
            call_count[0] += 1
            ctrl = _SessionWSControl()
            ctrl._bind(MagicMock())
            if call_count[0] <= max_reconnects:

                def failing():
                    yield f"chunk{call_count[0]}"
                    raise SandboxConnectionError("lost")

                return failing(), ctrl
            else:
                return _output_iter(["final"]), ctrl

        mock_connect.side_effect = make_connect

        session = Session("sess-1", sandbox)
        session.connect()

        with patch("time.sleep"):
            output = list(session)

        # Each reconnect yields data (resetting counter) then fails
        assert len(output) == max_reconnects + 1
        assert output[-1] == "final"
