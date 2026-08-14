"""CommandHandle / AsyncCommandHandle callback delivery across reconnects.

Output callbacks must be attached to the handle (which survives
auto-reconnects), not to a single WebSocket connection — otherwise every
chunk delivered after a mid-stream reconnect is silently dropped from the
on_stdout/on_stderr path while the result still reports exit_code 0.
"""

from unittest import mock

import pytest

from langsmith.sandbox._models import AsyncCommandHandle, CommandHandle


def _messages(*msgs):
    return iter(list(msgs))


async def _async_messages(*msgs):
    for msg in msgs:
        yield msg


def _mock_sandbox():
    return mock.MagicMock()


def _mock_async_sandbox():
    sandbox = mock.MagicMock()
    sandbox.reconnect = mock.AsyncMock()
    return sandbox


class TestCommandHandleCallbacks:
    def test_callbacks_invoked_for_every_chunk(self):
        stream = _messages(
            {"type": "started", "command_id": "cmd-1", "pid": 42},
            {"type": "stdout", "data": "out1", "offset": 0},
            {"type": "stderr", "data": "err1", "offset": 0},
            {"type": "stdout", "data": "out2", "offset": 4},
            {"type": "exit", "exit_code": 0},
        )
        stdout_data: list[str] = []
        stderr_data: list[str] = []

        handle = CommandHandle(
            stream,
            None,
            _mock_sandbox(),
            on_stdout=stdout_data.append,
            on_stderr=stderr_data.append,
        )
        result = handle.result

        assert result.exit_code == 0
        assert stdout_data == ["out1", "out2"]
        assert stderr_data == ["err1"]

    def test_callbacks_survive_reconnect(self):
        # First connection dies without an exit message; the reconnected
        # stream delivers the tail. Callbacks must see ALL chunks.
        stream = _messages(
            {"type": "started", "command_id": "cmd-1", "pid": 42},
            {"type": "stdout", "data": "before-disconnect ", "offset": 0},
        )
        sandbox = _mock_sandbox()
        reconnect_handle = mock.MagicMock()
        reconnect_handle._stream = _messages(
            {"type": "stdout", "data": "after-reconnect", "offset": 18},
            {"type": "exit", "exit_code": 0},
        )
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        stdout_data: list[str] = []
        handle = CommandHandle(
            stream,
            None,
            sandbox,
            on_stdout=stdout_data.append,
        )

        original_backoff = CommandHandle._BACKOFF_BASE
        CommandHandle._BACKOFF_BASE = 0
        try:
            result = handle.result
        finally:
            CommandHandle._BACKOFF_BASE = original_backoff

        assert result.exit_code == 0
        assert stdout_data == ["before-disconnect ", "after-reconnect"]
        assert result.stdout == "before-disconnect after-reconnect"


class TestAsyncCommandHandleCallbacks:
    @pytest.mark.asyncio
    async def test_callbacks_invoked_for_every_chunk(self):
        stream = _async_messages(
            {"type": "started", "command_id": "cmd-1", "pid": 42},
            {"type": "stdout", "data": "out1", "offset": 0},
            {"type": "stderr", "data": "err1", "offset": 0},
            {"type": "stdout", "data": "out2", "offset": 4},
            {"type": "exit", "exit_code": 0},
        )
        stdout_data: list[str] = []
        stderr_data: list[str] = []

        handle = AsyncCommandHandle(
            stream,
            None,
            _mock_async_sandbox(),
            on_stdout=stdout_data.append,
            on_stderr=stderr_data.append,
        )
        result = await handle.result

        assert result.exit_code == 0
        assert stdout_data == ["out1", "out2"]
        assert stderr_data == ["err1"]

    @pytest.mark.asyncio
    async def test_callbacks_survive_reconnect(self):
        stream = _async_messages(
            {"type": "started", "command_id": "cmd-1", "pid": 42},
            {"type": "stdout", "data": "before-disconnect ", "offset": 0},
        )
        sandbox = _mock_async_sandbox()
        reconnect_handle = mock.MagicMock()
        reconnect_handle._stream = _async_messages(
            {"type": "stdout", "data": "after-reconnect", "offset": 18},
            {"type": "exit", "exit_code": 0},
        )
        reconnect_handle._control = None
        sandbox.reconnect.return_value = reconnect_handle

        stdout_data: list[str] = []
        handle = AsyncCommandHandle(
            stream,
            None,
            sandbox,
            on_stdout=stdout_data.append,
        )
        original_backoff = AsyncCommandHandle._BACKOFF_BASE
        AsyncCommandHandle._BACKOFF_BASE = 0
        try:
            result = await handle.result
        finally:
            AsyncCommandHandle._BACKOFF_BASE = original_backoff

        assert result.exit_code == 0
        assert stdout_data == ["before-disconnect ", "after-reconnect"]
        assert result.stdout == "before-disconnect after-reconnect"
