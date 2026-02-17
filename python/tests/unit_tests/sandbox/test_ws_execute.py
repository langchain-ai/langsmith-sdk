"""Tests for WebSocket-based command execution."""

from __future__ import annotations

import json
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest

from langsmith.sandbox._exceptions import (
    CommandTimeoutError,
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._models import (
    CommandHandle,
    ExecutionResult,
    OutputChunk,
)
from langsmith.sandbox._ws_execute import (
    _build_auth_headers,
    _build_ws_url,
    _raise_from_error_msg,
    _WSStreamControl,
)

# =============================================================================
# Helper: fake message streams
# =============================================================================


def _make_stream(messages: list[dict]) -> Iterator[dict]:
    """Create a simple iterator over message dicts."""
    yield from messages


def _started_msg(command_id: str = "cmd-123", pid: int = 42) -> dict:
    return {"type": "started", "command_id": command_id, "pid": pid}


def _stdout_msg(data: str, offset: int = 0) -> dict:
    return {"type": "stdout", "data": data, "offset": offset}


def _stderr_msg(data: str, offset: int = 0) -> dict:
    return {"type": "stderr", "data": data, "offset": offset}


def _exit_msg(exit_code: int = 0) -> dict:
    return {"type": "exit", "exit_code": exit_code}


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
# Tests: CommandHandle
# =============================================================================


class TestCommandHandle:
    def _make_sandbox_mock(self):
        """Create a mock Sandbox."""
        sandbox = MagicMock()
        return sandbox

    def test_basic_flow(self):
        """started -> stdout -> stderr -> exit, with offset tracking."""
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("hello ", 0),
                _stdout_msg("world\n", 6),
                _stderr_msg("warn", 0),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)

        assert handle.command_id == "cmd-123"
        assert handle.pid == 42

        chunks = list(handle)
        assert len(chunks) == 3
        assert all(isinstance(c, OutputChunk) for c in chunks)
        assert chunks[0].stream == "stdout"
        assert chunks[0].data == "hello "
        assert chunks[1].data == "world\n"
        assert chunks[2].stream == "stderr"
        assert chunks[2].data == "warn"

        result = handle.result
        assert result.stdout == "hello world\n"
        assert result.stderr == "warn"
        assert result.exit_code == 0
        assert result.success is True

        # Offsets are tracked in bytes
        assert handle.last_stdout_offset == len("hello world\n".encode("utf-8"))
        assert handle.last_stderr_offset == len("warn".encode("utf-8"))

    def test_nonzero_exit_code(self):
        """Non-zero exit code sets success=False."""
        stream = _make_stream(
            [
                _started_msg(),
                _stderr_msg("error!\n", 0),
                _exit_msg(1),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        chunks = list(handle)
        assert len(chunks) == 1
        assert chunks[0].stream == "stderr"
        assert chunks[0].data == "error!\n"
        assert handle.result.stderr == "error!\n"
        assert handle.result.exit_code == 1
        assert handle.result.success is False

    def test_result_blocks(self):
        """Calling result without iterating should drain the stream."""
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("output"),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        result = handle.result
        assert result.stdout == "output"
        assert result.exit_code == 0

    def test_no_started_message(self):
        stream = _make_stream([_stdout_msg("data")])
        sandbox = self._make_sandbox_mock()
        with pytest.raises(SandboxOperationError, match="Expected 'started'"):
            CommandHandle(stream, None, sandbox)

    def test_empty_stream(self):
        stream = _make_stream([])
        sandbox = self._make_sandbox_mock()
        with pytest.raises(SandboxOperationError, match="before 'started'"):
            CommandHandle(stream, None, sandbox)

    def test_stream_ends_without_exit(self):
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("data"),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        list(handle)  # Exhaust
        with pytest.raises(SandboxOperationError, match="without exit"):
            _ = handle.result

    def test_kill(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        stream = _make_stream([_started_msg(), _exit_msg(0)])
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, ctrl, sandbox)
        handle.kill()
        ws.send.assert_called_once_with(json.dumps({"type": "kill"}))

    def test_send_input(self):
        ctrl = _WSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        stream = _make_stream([_started_msg(), _exit_msg(0)])
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, ctrl, sandbox)
        handle.send_input("data\n")
        ws.send.assert_called_once_with(json.dumps({"type": "input", "data": "data\n"}))

    def test_kill_no_control(self):
        """kill() is a no-op when control is None."""
        stream = _make_stream([_started_msg(), _exit_msg(0)])
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        handle.kill()  # Should not raise

    def test_double_iteration(self):
        """Second iteration over an exhausted handle yields nothing."""
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("data"),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        chunks1 = list(handle)
        chunks2 = list(handle)
        assert len(chunks1) == 1
        assert len(chunks2) == 0

    def test_offset_tracking_utf8(self):
        """Offsets are tracked in bytes, not characters."""
        # emoji is 4 bytes in UTF-8
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("😀", 0),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(stream, None, sandbox)
        list(handle)
        assert handle.last_stdout_offset == 4  # 😀 is 4 bytes

    def test_reconnect_on_connection_error(self):
        """Auto-reconnect on SandboxConnectionError with backoff."""

        def failing_stream():
            yield _started_msg()
            yield _stdout_msg("part1", 0)
            raise SandboxConnectionError("connection lost")

        sandbox = self._make_sandbox_mock()
        reconnect_handle = MagicMock()
        reconnect_handle._stream = _make_stream(
            [
                _stdout_msg("part2", 5),
                _exit_msg(0),
            ]
        )
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        handle = CommandHandle(failing_stream(), None, sandbox)

        with patch("time.sleep") as mock_sleep:
            chunks = list(handle)

        assert len(chunks) == 2
        assert chunks[0].data == "part1"
        assert chunks[1].data == "part2"
        sandbox.reconnect.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)

    def test_reconnect_on_1001_no_backoff(self):
        """SandboxServerReloadError triggers immediate reconnect (no sleep)."""

        def failing_stream():
            yield _started_msg()
            yield _stdout_msg("data", 0)
            raise SandboxServerReloadError("server reloading")

        sandbox = self._make_sandbox_mock()
        reconnect_handle = MagicMock()
        reconnect_handle._stream = _make_stream([_exit_msg(0)])
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        handle = CommandHandle(failing_stream(), None, sandbox)

        with patch("time.sleep") as mock_sleep:
            list(handle)
            mock_sleep.assert_not_called()  # No backoff for hot-reload

    def test_max_reconnects_exceeded(self):
        """Exceeding MAX_AUTO_RECONNECTS raises."""

        def always_failing():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()

        def make_failing_reconnect(*args, **kwargs):
            h = MagicMock()
            h._stream = always_failing_reconnect()
            h._control = None
            return h

        def always_failing_reconnect():
            raise SandboxConnectionError("lost again")
            yield  # Make it a generator  # noqa: E501

        sandbox.reconnect.side_effect = make_failing_reconnect

        handle = CommandHandle(always_failing(), None, sandbox)

        with patch("time.sleep"):
            with pytest.raises(SandboxConnectionError, match="giving up"):
                list(handle)

    def test_kill_guard(self):
        """No auto-reconnect after kill()."""
        ctrl = _WSStreamControl()
        ctrl._killed = True  # Simulate kill was called

        def failing_stream():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(failing_stream(), ctrl, sandbox)

        with pytest.raises(SandboxConnectionError):
            list(handle)

        sandbox.reconnect.assert_not_called()

    def test_reconnect_resets_counter(self):
        """Successful data between disconnects resets the reconnect counter.

        The counter resets to 0 every time a chunk arrives.  So if each
        reconnect yields at least one chunk before failing, the handle
        should survive more total reconnects than MAX_AUTO_RECONNECTS.
        """
        reconnect_count = [0]
        max_reconnects_to_do = CommandHandle.MAX_AUTO_RECONNECTS + 3

        def initial_stream():
            yield _started_msg()
            yield _stdout_msg("chunk0", 0)
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()

        def make_reconnect_handle(*args, **kwargs):
            reconnect_count[0] += 1
            h = MagicMock()
            if reconnect_count[0] < max_reconnects_to_do:
                # Each reconnect yields data then fails -> counter resets
                def reconnect_stream():
                    yield _stdout_msg(f"chunk{reconnect_count[0]}", 0)
                    raise SandboxConnectionError("lost again")

                h._stream = reconnect_stream()
            else:
                # Final reconnect: succeed
                h._stream = _make_stream(
                    [
                        _stdout_msg("final", 0),
                        _exit_msg(0),
                    ]
                )
            h._control = None
            return h

        sandbox.reconnect.side_effect = make_reconnect_handle
        handle = CommandHandle(initial_stream(), None, sandbox)

        with patch("time.sleep"):
            chunks = list(handle)

        # chunk0 + one chunk per reconnect (including final)
        assert len(chunks) == max_reconnects_to_do + 1
        assert reconnect_count[0] == max_reconnects_to_do

    def test_manual_reconnect(self):
        """handle.reconnect() delegates to sandbox.reconnect()."""
        stream = _make_stream(
            [
                _started_msg(),
                _stdout_msg("data", 0),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        sandbox.reconnect.return_value = MagicMock()

        handle = CommandHandle(stream, None, sandbox)
        list(handle)

        handle.reconnect()
        sandbox.reconnect.assert_called_once_with(
            "cmd-123",
            stdout_offset=handle.last_stdout_offset,
            stderr_offset=handle.last_stderr_offset,
        )

    def test_reconnect_with_explicit_command_id(self):
        """Reconnection handle with pre-set command_id."""
        stream = _make_stream(
            [
                _stdout_msg("data", 100),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = CommandHandle(
            stream,
            None,
            sandbox,
            command_id="existing-cmd",
            stdout_offset=100,
            stderr_offset=50,
        )
        assert handle.command_id == "existing-cmd"
        chunks = list(handle)
        assert len(chunks) == 1
        # offset from message (100) + len of data (4 bytes)
        assert handle.last_stdout_offset == 100 + len("data".encode("utf-8"))

    def test_session_expired_not_retried(self):
        """SandboxOperationError from reconnect() propagates (not retried)."""

        def failing_stream():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()
        sandbox.reconnect.side_effect = SandboxOperationError(
            "Session expired", operation="reconnect", error_type="SessionExpired"
        )

        handle = CommandHandle(failing_stream(), None, sandbox)

        with patch("time.sleep"):
            with pytest.raises(SandboxOperationError, match="Session expired"):
                list(handle)


# =============================================================================
# Tests: Sandbox.run() integration (with mocked WS)
# =============================================================================


class TestSandboxRunWs:
    """Test Sandbox.run() with mocked WebSocket layer."""

    def _make_sandbox(self) -> Any:
        """Create a Sandbox with mocked client."""
        from langsmith.sandbox._sandbox import Sandbox

        client = MagicMock()
        client._api_key = "test-key"
        return Sandbox.from_dict(
            data={
                "name": "test-sb",
                "template_name": "test-tmpl",
                "dataplane_url": "https://router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

    @patch("langsmith.sandbox._ws_execute.run_ws_stream")
    def test_run_default_ws(self, mock_run_ws):
        """Default run() uses WS and returns ExecutionResult."""
        mock_run_ws.return_value = (
            _make_stream(
                [
                    _started_msg(),
                    _stdout_msg("output"),
                    _exit_msg(0),
                ]
            ),
            _WSStreamControl(),
        )
        sandbox = self._make_sandbox()
        result = sandbox.run("echo hello")

        assert isinstance(result, ExecutionResult)
        assert result.stdout == "output"
        assert result.exit_code == 0

    @patch("langsmith.sandbox._ws_execute.run_ws_stream")
    def test_run_wait_false(self, mock_run_ws):
        """wait=False returns CommandHandle."""
        mock_run_ws.return_value = (
            _make_stream(
                [
                    _started_msg(),
                    _stdout_msg("data"),
                    _exit_msg(0),
                ]
            ),
            _WSStreamControl(),
        )
        sandbox = self._make_sandbox()
        handle = sandbox.run("make build", wait=False)

        assert isinstance(handle, CommandHandle)
        assert handle.command_id == "cmd-123"
        chunks = list(handle)
        assert len(chunks) == 1

    @patch("langsmith.sandbox._ws_execute.run_ws_stream")
    def test_run_callbacks(self, mock_run_ws):
        """Callbacks are invoked during WS stream."""
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        # Need to capture callbacks in the mock
        def fake_run_ws(url, key, cmd, **kwargs):
            on_stdout = kwargs.get("on_stdout")
            on_stderr = kwargs.get("on_stderr")

            def stream():
                yield _started_msg()
                msg = _stdout_msg("out")
                if on_stdout:
                    on_stdout(msg["data"])
                yield msg
                msg = _stderr_msg("err")
                if on_stderr:
                    on_stderr(msg["data"])
                yield msg
                yield _exit_msg(0)

            return stream(), _WSStreamControl()

        mock_run_ws.side_effect = fake_run_ws
        sandbox = self._make_sandbox()
        result = sandbox.run(
            "cmd",
            on_stdout=stdout_chunks.append,
            on_stderr=stderr_chunks.append,
        )

        assert isinstance(result, ExecutionResult)
        assert stdout_chunks == ["out"]
        assert stderr_chunks == ["err"]

    def test_run_wait_false_plus_callbacks_raises(self):
        """wait=False + callbacks raises ValueError."""
        sandbox = self._make_sandbox()
        with pytest.raises(ValueError, match="Cannot combine"):
            sandbox.run("cmd", wait=False, on_stdout=lambda s: None)

    @pytest.mark.parametrize(
        "exc",
        [
            SandboxConnectionError("WS failed"),
            ImportError("no websockets"),
        ],
    )
    @patch("langsmith.sandbox._ws_execute.run_ws_stream")
    def test_run_fallback_to_http(self, mock_run_ws, exc):
        """WS failure (connection error or missing lib) falls back to HTTP."""
        mock_run_ws.side_effect = exc
        sandbox = self._make_sandbox()

        with patch.object(sandbox, "_run_http") as mock_http:
            mock_http.return_value = ExecutionResult(
                stdout="http output", stderr="", exit_code=0
            )
            result = sandbox.run("echo hello")

        assert result.stdout == "http output"
        mock_http.assert_called_once()

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"wait": False},
            {"on_stdout": lambda s: None},
        ],
    )
    @patch("langsmith.sandbox._ws_execute.run_ws_stream")
    def test_run_no_fallback_on_streaming(self, mock_run_ws, kwargs):
        """wait=False or callbacks prevents HTTP fallback."""
        mock_run_ws.side_effect = SandboxConnectionError("WS failed")
        sandbox = self._make_sandbox()

        with pytest.raises(SandboxConnectionError):
            sandbox.run("cmd", **kwargs)


# =============================================================================
# Tests: Sandbox.reconnect()
# =============================================================================


class TestSandboxReconnect:
    def _make_sandbox(self):
        from langsmith.sandbox._sandbox import Sandbox

        client = MagicMock()
        client._api_key = "test-key"
        return Sandbox.from_dict(
            data={
                "name": "test-sb",
                "template_name": "test-tmpl",
                "dataplane_url": "https://router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

    @patch("langsmith.sandbox._ws_execute.reconnect_ws_stream")
    def test_reconnect(self, mock_reconnect_ws):
        """Reconnect returns a CommandHandle and forwards offsets."""
        mock_reconnect_ws.return_value = (
            _make_stream(
                [
                    _stdout_msg("replayed", 0),
                    _exit_msg(0),
                ]
            ),
            _WSStreamControl(),
        )
        sandbox = self._make_sandbox()
        handle = sandbox.reconnect(
            "cmd-123",
            stdout_offset=100,
            stderr_offset=50,
        )

        assert isinstance(handle, CommandHandle)
        assert handle.command_id == "cmd-123"
        chunks = list(handle)
        assert len(chunks) == 1
        assert chunks[0].data == "replayed"

        mock_reconnect_ws.assert_called_once_with(
            "https://router.example.com/sb-123",
            "test-key",
            "cmd-123",
            stdout_offset=100,
            stderr_offset=50,
        )


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
