"""Idempotent retry when a command WebSocket closes before 'started'.

A proxied exec tunnel can be torn down gracefully before the guest emits its
'started' frame. Because run() sends a client-generated command_id and the
server does get-or-create keyed on it, re-issuing the command reattaches to the
same session instead of spawning a second one -- but only once the daemon has
proven it honors the id (by echoing it back in a prior 'started').
"""

from unittest import mock

import pytest

from langsmith.sandbox import (
    AsyncSandboxClient,
    SandboxClient,
    SandboxOperationError,
)
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._models import (
    CommandHandle,
    _StreamEndedBeforeStarted,
)
from langsmith.sandbox._sandbox import Sandbox


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)


def _client():
    return SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)


def _sandbox():
    return Sandbox.from_dict(
        data={
            "name": "sb",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=_client(),
        auto_delete=False,
    )


def _empty():
    return iter(())


def _started_then_exit(command_id):
    return iter(
        [
            {"type": "started", "command_id": command_id, "pid": 1},
            {"type": "exit", "exit_code": 0},
        ]
    )


class TestStartedEcho:
    def test_matching_echo_marks_supported(self):
        sandbox = _sandbox()
        CommandHandle(
            _started_then_exit("cid-1"),
            None,
            sandbox,
            sent_command_id="cid-1",
        )
        assert sandbox._client_command_id_honored is True

    def test_mismatched_echo_marks_unsupported(self):
        sandbox = _sandbox()
        CommandHandle(
            _started_then_exit("server-assigned"),
            None,
            sandbox,
            sent_command_id="cid-1",
        )
        assert sandbox._client_command_id_honored is False

    def test_empty_stream_raises_marker(self):
        with pytest.raises(_StreamEndedBeforeStarted):
            CommandHandle(_empty(), None, _sandbox(), sent_command_id="cid-1")


class TestSyncRetry:
    def test_retries_with_same_command_id_when_supported(self, monkeypatch):
        sandbox = _sandbox()
        sandbox._client_command_id_honored = True  # proven by a prior command
        calls: list[dict] = []

        def fake_run_ws_stream(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return _empty(), None
            return _started_then_exit(kwargs["command_id"]), None

        monkeypatch.setattr(
            "langsmith.sandbox._ws_execute.run_ws_stream", fake_run_ws_stream
        )

        result = sandbox.run("echo hi")

        assert result.exit_code == 0
        assert len(calls) == 2
        # Same id across the retry -> server dedupes, no double-run.
        assert calls[0]["command_id"] == calls[1]["command_id"]

    def test_no_retry_when_capability_unknown(self, monkeypatch):
        sandbox = _sandbox()  # _client_command_id_honored is None
        calls: list[dict] = []

        def fake_run_ws_stream(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            return _empty(), None

        monkeypatch.setattr(
            "langsmith.sandbox._ws_execute.run_ws_stream", fake_run_ws_stream
        )

        with pytest.raises(SandboxOperationError):
            sandbox.run("echo hi", wait=False)
        assert len(calls) == 1

    def test_gives_up_after_max_attempts(self, monkeypatch):
        sandbox = _sandbox()
        sandbox._client_command_id_honored = True
        calls: list[dict] = []

        def fake_run_ws_stream(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            return _empty(), None

        monkeypatch.setattr(
            "langsmith.sandbox._ws_execute.run_ws_stream", fake_run_ws_stream
        )

        with pytest.raises(_StreamEndedBeforeStarted):
            sandbox.run("echo hi", wait=False)
        assert len(calls) == CommandHandle.MAX_AUTO_RECONNECTS + 1


def _async_sandbox():
    client = AsyncSandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    return AsyncSandbox.from_dict(
        data={
            "name": "sb",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=client,
        auto_delete=False,
    )


async def _aempty():
    return
    yield  # make it an async generator


async def _astarted_then_exit(command_id):
    yield {"type": "started", "command_id": command_id, "pid": 1}
    yield {"type": "exit", "exit_code": 0}


class TestAsyncRetry:
    async def test_retries_with_same_command_id_when_supported(self, monkeypatch):
        sandbox = _async_sandbox()
        sandbox._client_command_id_honored = True
        calls: list[dict] = []

        async def fake(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return _aempty(), None
            return _astarted_then_exit(kwargs["command_id"]), None

        monkeypatch.setattr("asyncio.sleep", mock.AsyncMock())
        monkeypatch.setattr("langsmith.sandbox._ws_execute.run_ws_stream_async", fake)

        result = await sandbox.run("echo hi")

        assert result.exit_code == 0
        assert len(calls) == 2
        assert calls[0]["command_id"] == calls[1]["command_id"]

    async def test_no_retry_when_capability_unknown(self, monkeypatch):
        sandbox = _async_sandbox()
        calls: list[dict] = []

        async def fake(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            return _aempty(), None

        monkeypatch.setattr("langsmith.sandbox._ws_execute.run_ws_stream_async", fake)

        with pytest.raises(SandboxOperationError):
            await sandbox.run("echo hi", wait=False)
        assert len(calls) == 1
