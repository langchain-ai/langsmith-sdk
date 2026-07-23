"""Idempotent retry when a command WebSocket closes before 'started'.

A proxied exec tunnel can be torn down gracefully before the guest emits its
'started' frame. run() sends a client-generated command_id and the server does
get-or-create keyed on it, so re-issuing the same command reattaches to the
existing session instead of spawning a second one.
"""

import pytest

from langsmith.sandbox import (
    AsyncSandboxClient,
    SandboxClient,
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


def _sandbox():
    return Sandbox.from_dict(
        data={
            "name": "sb",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=SandboxClient(api_endpoint="http://test-server:8080", max_retries=0),
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


class TestCommandHandle:
    def test_empty_stream_raises_marker(self):
        with pytest.raises(_StreamEndedBeforeStarted):
            CommandHandle(_empty(), None, _sandbox())


class TestSyncRetry:
    def test_retries_with_same_command_id(self, monkeypatch):
        sandbox = _sandbox()
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

    def test_gives_up_after_max_attempts(self, monkeypatch):
        sandbox = _sandbox()
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
    async def test_retries_with_same_command_id(self, monkeypatch):
        sandbox = _async_sandbox()
        calls: list[dict] = []

        async def fake(dataplane_url, api_key, command, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return _aempty(), None
            return _astarted_then_exit(kwargs["command_id"]), None

        async def _no_sleep(_s):
            return None

        monkeypatch.setattr("asyncio.sleep", _no_sleep)
        monkeypatch.setattr("langsmith.sandbox._ws_execute.run_ws_stream_async", fake)

        result = await sandbox.run("echo hi")

        assert result.exit_code == 0
        assert len(calls) == 2
        assert calls[0]["command_id"] == calls[1]["command_id"]
