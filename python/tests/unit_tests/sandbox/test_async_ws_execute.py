"""Tests for AsyncCommandHandle (async WebSocket command execution)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._models import (
    AsyncCommandHandle,
    ExecutionResult,
    OutputChunk,
)
from langsmith.sandbox._ws_execute import _AsyncWSStreamControl

# =============================================================================
# Helper: async fake message streams
# =============================================================================


async def _make_async_stream(
    messages: list[dict],
) -> AsyncIterator[dict]:
    """Create an async iterator over message dicts."""
    for msg in messages:
        yield msg


def _started_msg(command_id: str = "cmd-123", pid: int = 42) -> dict:
    return {"type": "started", "command_id": command_id, "pid": pid}


def _stdout_msg(data: str, offset: int = 0) -> dict:
    return {"type": "stdout", "data": data, "offset": offset}


def _stderr_msg(data: str, offset: int = 0) -> dict:
    return {"type": "stderr", "data": data, "offset": offset}


def _exit_msg(exit_code: int = 0) -> dict:
    return {"type": "exit", "exit_code": exit_code}


# =============================================================================
# Tests: AsyncCommandHandle
# =============================================================================


class TestAsyncCommandHandle:
    def _make_sandbox_mock(self):
        """Create a mock AsyncSandbox."""
        sandbox = MagicMock()
        sandbox.reconnect = AsyncMock()
        return sandbox

    @pytest.mark.asyncio
    async def test_basic_flow(self):
        """started -> stdout -> stderr -> exit, with offset tracking."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("hello ", 0),
                _stdout_msg("world\n", 6),
                _stderr_msg("warn", 0),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()

        assert handle.command_id == "cmd-123"
        assert handle.pid == 42

        chunks = [c async for c in handle]
        assert len(chunks) == 3
        assert all(isinstance(c, OutputChunk) for c in chunks)
        assert chunks[0].stream == "stdout"
        assert chunks[0].data == "hello "
        assert chunks[1].data == "world\n"
        assert chunks[2].stream == "stderr"
        assert chunks[2].data == "warn"

        result = await handle.result
        assert result.stdout == "hello world\n"
        assert result.stderr == "warn"
        assert result.exit_code == 0
        assert result.success is True

        # Offsets are tracked in bytes
        assert handle.last_stdout_offset == len("hello world\n".encode("utf-8"))
        assert handle.last_stderr_offset == len("warn".encode("utf-8"))

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self):
        """Non-zero exit code sets success=False."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stderr_msg("error!\n", 0),
                _exit_msg(1),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()

        chunks = [c async for c in handle]
        assert len(chunks) == 1
        assert chunks[0].stream == "stderr"
        assert chunks[0].data == "error!\n"

        result = await handle.result
        assert result.stderr == "error!\n"
        assert result.exit_code == 1
        assert result.success is False

    @pytest.mark.asyncio
    async def test_result_drains_stream(self):
        """Calling result without iterating should drain the stream."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("output"),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()

        result = await handle.result
        assert result.stdout == "output"
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_no_started_message(self):
        stream = _make_async_stream([_stdout_msg("data")])
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        with pytest.raises(SandboxOperationError, match="Expected 'started'"):
            await handle._ensure_started()

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        stream = _make_async_stream([])
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        with pytest.raises(SandboxOperationError, match="before 'started'"):
            await handle._ensure_started()

    @pytest.mark.asyncio
    async def test_stream_ends_without_exit(self):
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("data"),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()

        _ = [c async for c in handle]  # Exhaust
        with pytest.raises(SandboxOperationError, match="without exit"):
            await handle.result

    @pytest.mark.asyncio
    async def test_kill(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()

        async def mock_send(data):
            pass

        ws.send = mock_send
        ctrl._bind(ws)

        stream = _make_async_stream(
            [
                _started_msg(),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, ctrl, sandbox)
        await handle._ensure_started()
        await handle.kill()
        assert ctrl.killed is True

    @pytest.mark.asyncio
    async def test_send_input(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data):
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)

        stream = _make_async_stream(
            [
                _started_msg(),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, ctrl, sandbox)
        await handle._ensure_started()
        await handle.send_input("data\n")
        assert json.loads(sent[0]) == {
            "type": "input",
            "data": "data\n",
        }

    @pytest.mark.asyncio
    async def test_kill_no_control(self):
        """kill() is a no-op when control is None."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()
        await handle.kill()  # Should not raise

    @pytest.mark.asyncio
    async def test_double_iteration(self):
        """Second iteration over an exhausted handle yields nothing."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("data"),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()

        chunks1 = [c async for c in handle]
        chunks2 = [c async for c in handle]
        assert len(chunks1) == 1
        assert len(chunks2) == 0

    @pytest.mark.asyncio
    async def test_offset_tracking_utf8(self):
        """Offsets are tracked in bytes, not characters."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("\U0001f600", 0),  # 4 bytes
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()
        _ = [c async for c in handle]
        assert handle.last_stdout_offset == 4

    @pytest.mark.asyncio
    async def test_reconnect_on_connection_error(self):
        """Auto-reconnect on SandboxConnectionError with backoff."""

        async def failing_stream():
            yield _started_msg()
            yield _stdout_msg("part1", 0)
            raise SandboxConnectionError("connection lost")

        sandbox = self._make_sandbox_mock()
        reconnect_handle = MagicMock()
        reconnect_handle._stream = _make_async_stream(
            [
                _stdout_msg("part2", 5),
                _exit_msg(0),
            ]
        )
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        handle = AsyncCommandHandle(failing_stream(), None, sandbox)
        await handle._ensure_started()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            chunks = [c async for c in handle]

        assert len(chunks) == 2
        assert chunks[0].data == "part1"
        assert chunks[1].data == "part2"
        sandbox.reconnect.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)

    @pytest.mark.asyncio
    async def test_reconnect_on_1001_no_backoff(self):
        """SandboxServerReloadError triggers immediate reconnect."""

        async def failing_stream():
            yield _started_msg()
            yield _stdout_msg("data", 0)
            raise SandboxServerReloadError("server reloading")

        sandbox = self._make_sandbox_mock()
        reconnect_handle = MagicMock()
        reconnect_handle._stream = _make_async_stream([_exit_msg(0)])
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        handle = AsyncCommandHandle(failing_stream(), None, sandbox)
        await handle._ensure_started()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            _ = [c async for c in handle]
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_reconnects_exceeded(self):
        """Exceeding MAX_AUTO_RECONNECTS raises."""

        async def always_failing():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()

        async def always_failing_reconnect():
            raise SandboxConnectionError("lost again")
            yield  # Make it an async generator  # noqa: E501

        def make_failing_reconnect(*args, **kwargs):
            h = MagicMock()
            h._stream = always_failing_reconnect()
            h._control = None
            return h

        sandbox.reconnect.side_effect = make_failing_reconnect

        handle = AsyncCommandHandle(always_failing(), None, sandbox)
        await handle._ensure_started()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SandboxConnectionError, match="giving up"):
                _ = [c async for c in handle]

    @pytest.mark.asyncio
    async def test_kill_guard(self):
        """No auto-reconnect after kill()."""
        ctrl = _AsyncWSStreamControl()
        ctrl._killed = True

        async def failing_stream():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(
            failing_stream(),
            ctrl,
            sandbox,
        )
        await handle._ensure_started()

        with pytest.raises(SandboxConnectionError):
            _ = [c async for c in handle]

        sandbox.reconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnect_resets_counter(self):
        """Successful data between disconnects resets the counter.

        The counter resets to 0 every time a chunk arrives. So if each
        reconnect yields at least one chunk before failing, the handle
        should survive more total reconnects than MAX_AUTO_RECONNECTS.
        """
        reconnect_count = [0]
        max_reconnects_to_do = AsyncCommandHandle.MAX_AUTO_RECONNECTS + 3

        async def initial_stream():
            yield _started_msg()
            yield _stdout_msg("chunk0", 0)
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()

        def make_reconnect_handle(*args, **kwargs):
            reconnect_count[0] += 1
            h = MagicMock()
            if reconnect_count[0] < max_reconnects_to_do:

                async def reconnect_stream():
                    yield _stdout_msg(
                        f"chunk{reconnect_count[0]}",
                        0,
                    )
                    raise SandboxConnectionError("lost again")

                h._stream = reconnect_stream()
            else:
                h._stream = _make_async_stream(
                    [
                        _stdout_msg("final", 0),
                        _exit_msg(0),
                    ]
                )
            h._control = None
            return h

        sandbox.reconnect.side_effect = make_reconnect_handle
        handle = AsyncCommandHandle(
            initial_stream(),
            None,
            sandbox,
        )
        await handle._ensure_started()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            chunks = [c async for c in handle]

        assert len(chunks) == max_reconnects_to_do + 1
        assert reconnect_count[0] == max_reconnects_to_do

    @pytest.mark.asyncio
    async def test_reconnect_with_explicit_command_id(self):
        """Reconnection handle with pre-set command_id."""
        stream = _make_async_stream(
            [
                _stdout_msg("data", 100),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        handle = AsyncCommandHandle(
            stream,
            None,
            sandbox,
            command_id="existing-cmd",
            stdout_offset=100,
            stderr_offset=50,
        )
        assert handle.command_id == "existing-cmd"
        chunks = [c async for c in handle]
        assert len(chunks) == 1
        assert handle.last_stdout_offset == 100 + len("data".encode("utf-8"))

    @pytest.mark.asyncio
    async def test_session_expired_not_retried(self):
        """SandboxOperationError propagates (not retried)."""

        async def failing_stream():
            yield _started_msg()
            raise SandboxConnectionError("lost")

        sandbox = self._make_sandbox_mock()
        sandbox.reconnect.side_effect = SandboxOperationError(
            "Session expired",
            operation="reconnect",
            error_type="SessionExpired",
        )

        handle = AsyncCommandHandle(
            failing_stream(),
            None,
            sandbox,
        )
        await handle._ensure_started()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SandboxOperationError, match="Session expired"):
                _ = [c async for c in handle]

    @pytest.mark.asyncio
    async def test_manual_reconnect(self):
        """handle.reconnect() delegates to sandbox.reconnect()."""
        stream = _make_async_stream(
            [
                _started_msg(),
                _stdout_msg("data", 0),
                _exit_msg(0),
            ]
        )
        sandbox = self._make_sandbox_mock()
        sandbox.reconnect.return_value = MagicMock()

        handle = AsyncCommandHandle(stream, None, sandbox)
        await handle._ensure_started()
        _ = [c async for c in handle]

        await handle.reconnect()
        sandbox.reconnect.assert_called_once_with(
            "cmd-123",
            stdout_offset=handle.last_stdout_offset,
            stderr_offset=handle.last_stderr_offset,
        )


# =============================================================================
# Tests: _AsyncWSStreamControl
# =============================================================================


class TestAsyncWSStreamControl:
    def test_initial_state(self):
        ctrl = _AsyncWSStreamControl()
        assert ctrl.killed is False

    def test_bind_unbind(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        assert ctrl._ws is ws
        ctrl._unbind()
        assert ctrl._ws is None
        assert ctrl._closed is True

    @pytest.mark.asyncio
    async def test_send_kill(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        await ctrl.send_kill()
        assert ctrl.killed is True
        assert json.loads(sent[0]) == {"type": "kill"}

    @pytest.mark.asyncio
    async def test_send_kill_when_closed(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        ctrl._unbind()
        await ctrl.send_kill()
        assert ctrl.killed is True
        assert sent == []

    @pytest.mark.asyncio
    async def test_send_input(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        await ctrl.send_input("hello\n")
        assert json.loads(sent[0]) == {
            "type": "input",
            "data": "hello\n",
        }


# =============================================================================
# Tests: AsyncSandbox.run() integration (with mocked WS)
# =============================================================================


class TestAsyncSandboxRunWs:
    """Test AsyncSandbox.run() with mocked WebSocket layer."""

    def _make_sandbox(self) -> Any:
        """Create an AsyncSandbox with mocked client."""
        from langsmith.sandbox._async_sandbox import AsyncSandbox

        client = MagicMock()
        client._api_key = "test-key"
        return AsyncSandbox.from_dict(
            data={
                "name": "test-sb",
                "template_name": "test-tmpl",
                "dataplane_url": "https://router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._ws_execute.run_ws_stream_async")
    async def test_run_default_ws(self, mock_run_ws):
        """Default run() uses WS and returns ExecutionResult."""

        async def fake_ws(*args, **kwargs):
            return (
                _make_async_stream(
                    [
                        _started_msg(),
                        _stdout_msg("output"),
                        _exit_msg(0),
                    ]
                ),
                _AsyncWSStreamControl(),
            )

        mock_run_ws.side_effect = fake_ws
        sandbox = self._make_sandbox()
        result = await sandbox.run("echo hello")

        assert isinstance(result, ExecutionResult)
        assert result.stdout == "output"
        assert result.exit_code == 0

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._ws_execute.run_ws_stream_async")
    async def test_run_wait_false(self, mock_run_ws):
        """wait=False returns AsyncCommandHandle."""

        async def fake_ws(*args, **kwargs):
            return (
                _make_async_stream(
                    [
                        _started_msg(),
                        _stdout_msg("data"),
                        _exit_msg(0),
                    ]
                ),
                _AsyncWSStreamControl(),
            )

        mock_run_ws.side_effect = fake_ws
        sandbox = self._make_sandbox()
        handle = await sandbox.run("make build", wait=False)

        assert isinstance(handle, AsyncCommandHandle)
        assert handle.command_id == "cmd-123"
        chunks = [c async for c in handle]
        assert len(chunks) == 1

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._ws_execute.run_ws_stream_async")
    async def test_run_callbacks(self, mock_run_ws):
        """Callbacks are invoked during WS stream."""
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def fake_ws(url, key, cmd, **kwargs):
            on_stdout = kwargs.get("on_stdout")
            on_stderr = kwargs.get("on_stderr")

            async def stream():
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

            return stream(), _AsyncWSStreamControl()

        mock_run_ws.side_effect = fake_ws
        sandbox = self._make_sandbox()
        result = await sandbox.run(
            "cmd",
            on_stdout=stdout_chunks.append,
            on_stderr=stderr_chunks.append,
        )

        assert isinstance(result, ExecutionResult)
        assert stdout_chunks == ["out"]
        assert stderr_chunks == ["err"]

    @pytest.mark.asyncio
    async def test_run_wait_false_plus_callbacks_raises(self):
        """wait=False + callbacks raises ValueError."""
        sandbox = self._make_sandbox()
        with pytest.raises(ValueError, match="Cannot combine"):
            await sandbox.run(
                "cmd",
                wait=False,
                on_stdout=lambda s: None,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            SandboxConnectionError("WS failed"),
            ImportError("no websockets"),
        ],
    )
    @patch("langsmith.sandbox._ws_execute.run_ws_stream_async")
    async def test_run_fallback_to_http(self, mock_run_ws, exc):
        """WS failure (connection error or missing lib) falls back to HTTP."""
        mock_run_ws.side_effect = exc
        sandbox = self._make_sandbox()

        with patch.object(sandbox, "_run_http", new_callable=AsyncMock) as mock_http:
            mock_http.return_value = ExecutionResult(
                stdout="http output",
                stderr="",
                exit_code=0,
            )
            result = await sandbox.run("echo hello")

        assert result.stdout == "http output"
        mock_http.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"wait": False},
            {"on_stdout": lambda s: None},
        ],
    )
    @patch("langsmith.sandbox._ws_execute.run_ws_stream_async")
    async def test_run_no_fallback_on_streaming(self, mock_run_ws, kwargs):
        """wait=False or callbacks prevents HTTP fallback."""
        mock_run_ws.side_effect = SandboxConnectionError("WS failed")
        sandbox = self._make_sandbox()

        with pytest.raises(SandboxConnectionError):
            await sandbox.run("cmd", **kwargs)


# =============================================================================
# Tests: AsyncSandbox.reconnect()
# =============================================================================


class TestAsyncSandboxReconnect:
    def _make_sandbox(self) -> Any:
        from langsmith.sandbox._async_sandbox import AsyncSandbox

        client = MagicMock()
        client._api_key = "test-key"
        return AsyncSandbox.from_dict(
            data={
                "name": "test-sb",
                "template_name": "test-tmpl",
                "dataplane_url": "https://router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._ws_execute.reconnect_ws_stream_async")
    async def test_reconnect(self, mock_reconnect_ws):
        """Reconnect returns an AsyncCommandHandle and forwards offsets."""

        async def fake_reconnect(*args, **kwargs):
            return (
                _make_async_stream(
                    [
                        _stdout_msg("replayed", 0),
                        _exit_msg(0),
                    ]
                ),
                _AsyncWSStreamControl(),
            )

        mock_reconnect_ws.side_effect = fake_reconnect
        sandbox = self._make_sandbox()
        handle = await sandbox.reconnect(
            "cmd-123",
            stdout_offset=100,
            stderr_offset=50,
        )

        assert isinstance(handle, AsyncCommandHandle)
        assert handle.command_id == "cmd-123"
        chunks = [c async for c in handle]
        assert len(chunks) == 1
        assert chunks[0].data == "replayed"

        mock_reconnect_ws.assert_called_once_with(
            "https://router.example.com/sb-123",
            "test-key",
            "cmd-123",
            stdout_offset=100,
            stderr_offset=50,
        )
