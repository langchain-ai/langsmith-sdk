"""Tests for the SSE exec transport (/execute/stream/{start,resume}).

Requests are served through httpx's MockTransport rather than pytest-httpx so
the tests hold whichever HTTPX backend the SDK selected.
"""

import json

import pytest

from langsmith import _features
from langsmith._openapi_client._httpx import httpx
from langsmith.sandbox import (
    CommandTimeoutError,
    SandboxClient,
    SandboxConnectionError,
    SandboxOperationError,
)
from langsmith.sandbox._async_client import AsyncSandboxClient
from langsmith.sandbox._async_sandbox import AsyncSandbox
from langsmith.sandbox._sandbox import Sandbox
from langsmith.sandbox._sse_execute import _ChunkDecoder, _iter_sse

from ._sse_fixtures import SSE_HEADERS, out, sse_bytes, started

DATAPLANE = "https://sandbox-router.example.com/sb-123"
START_PATH = "/sb-123/execute/stream/start"
RESUME_PATH = "/sb-123/execute/stream/resume"


class Server:
    """Serves queued responses per path and records the requests."""

    def __init__(self) -> None:
        self.queued: dict[str, list[httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def on(self, path: str, response: httpx.Response) -> None:
        self.queued.setdefault(path, []).append(response)

    def bodies(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self.queued.get(request.url.path)
        if not queue:
            return httpx.Response(500, json={"detail": {"message": "unexpected"}})
        # The last queued response answers every further request, so a retry
        # loop has something to read instead of failing on an empty queue.
        return queue.pop(0) if len(queue) > 1 else queue[0]


def sse(*events: tuple[str, object]) -> httpx.Response:
    return httpx.Response(200, content=sse_bytes(*events), headers=SSE_HEADERS)


@pytest.fixture(autouse=True)
def sse_feature(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_features.ENV_VAR, _features.SANDBOX_SSE_EXEC)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("langsmith.sandbox._sse_execute._resume_delay", lambda _: 0.0)


@pytest.fixture
def server() -> Server:
    return Server()


@pytest.fixture
def sandbox(server: Server):
    client = SandboxClient(
        api_endpoint="http://test-server:8080", api_key="test-key", max_retries=0
    )
    client._http = httpx.Client(transport=httpx.MockTransport(server.handle))
    return Sandbox.from_dict(
        data={"name": "test-sandbox", "dataplane_url": DATAPLANE},
        client=client,
        auto_delete=False,
    )


@pytest.fixture
def async_sandbox(server: Server):
    client = AsyncSandboxClient(
        api_endpoint="http://test-server:8080", api_key="test-key", max_retries=0
    )
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(server.handle))
    return AsyncSandbox.from_dict(
        data={"name": "test-sandbox", "dataplane_url": DATAPLANE},
        client=client,
        auto_delete=False,
    )


class TestSSEParsing:
    def test_skips_comments_and_joins_multiline_data(self):
        lines = iter([": ping", "", "event: exit", "data: {", 'data: "a": 1}', ""])
        assert list(_iter_sse(lines)) == [("exit", '{\n"a": 1}')]

    def test_trailing_event_without_blank_line(self):
        lines = iter(["event: exit", "data: {}"])
        assert list(_iter_sse(lines)) == [("exit", "{}")]


class TestChunkDecoder:
    def test_multibyte_character_split_across_chunks(self):
        decoder = _ChunkDecoder()
        # "é" is 0xC3 0xA9, so the first chunk ends mid-character.
        assert decoder.feed(0, b"a\xc3") == (0, "a")
        assert decoder.feed(2, b"\xa9b") == (1, "éb")

    def test_holds_back_until_a_character_completes(self):
        decoder = _ChunkDecoder()
        assert decoder.feed(0, b"\xf0\x9f") is None
        assert decoder.feed(2, b"\x98\x80") == (0, "\U0001f600")

    def test_invalid_bytes_are_replaced_not_held(self):
        decoder = _ChunkDecoder()
        assert decoder.feed(0, b"a\xffb") == (0, "a�b")

    def test_flush_emits_a_character_the_stream_never_completed(self):
        decoder = _ChunkDecoder()
        assert decoder.feed(0, b"ab\xc3") == (0, "ab")

        assert decoder.flush() == (2, "�")

    def test_flush_is_idempotent_and_empty_when_nothing_is_held(self):
        decoder = _ChunkDecoder()
        assert decoder.flush() is None
        assert decoder.feed(0, b"\xc3") is None
        assert decoder.flush() == (0, "�")
        assert decoder.flush() is None


class TestRun:
    def test_streams_output_and_exit(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"hello ")),
                ("stderr", out(0, b"warn")),
                ("stdout", out(6, b"world")),
                ("stream_end", {"stream": "stdout", "offset": 11}),
                ("stream_end", {"stream": "stderr", "offset": 4}),
                ("exit", {"exit_code": 0}),
            ),
        )

        result = sandbox.run("echo hi")

        assert result.stdout == "hello world"
        assert result.stderr == "warn"
        assert result.exit_code == 0

    def test_start_request_shape(self, server: Server, sandbox):
        server.on(START_PATH, sse(started(), ("exit", {"exit_code": 7})))

        assert sandbox.run("ls", timeout=30, ttl_seconds=90).exit_code == 7

        body = server.bodies()[0]
        assert body["command"] == "ls"
        assert body["timeout_seconds"] == 30
        assert body["ttl_seconds"] == 90
        assert body["command_id"]

    def test_run_config_is_forwarded(self, server: Server, sandbox):
        server.on(START_PATH, sse(started(), ("exit", {"exit_code": 0})))

        sandbox.run("ls", run_config={"user": "app", "work_dir": "/w"})

        assert server.bodies()[0]["run_config"] == {"user": "app", "work_dir": "/w"}

    def test_ack_required_resumes_from_reported_offsets(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"part-one ")),
                ("ack_required", {"stdout_offset": 9, "stderr_offset": 0}),
            ),
        )
        server.on(
            RESUME_PATH,
            sse(started(), ("stdout", out(9, b"part-two")), ("exit", {"exit_code": 0})),
        )

        result = sandbox.run("big")

        assert result.stdout == "part-one part-two"
        assert server.bodies()[1] == {
            "command_id": "cmd-1",
            "stdout_offset": 9,
            "stderr_offset": 0,
        }

    def test_handle_iteration_hides_the_resume(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"a")),
                ("ack_required", {"stdout_offset": 1, "stderr_offset": 0}),
            ),
        )
        server.on(
            RESUME_PATH,
            sse(started(), ("stdout", out(1, b"b")), ("exit", {"exit_code": 0})),
        )

        handle = sandbox.run("big", wait=False)

        assert handle.command_id == "cmd-1"
        assert handle.pid == 42
        assert [chunk.data for chunk in handle] == ["a", "b"]
        assert handle.result.exit_code == 0

    def test_server_shutdown_error_resumes(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"a")),
                (
                    "error",
                    {"error": "shutting down", "error_type": "ServerShuttingDown"},
                ),
            ),
        )
        server.on(
            RESUME_PATH,
            sse(started(), ("stdout", out(1, b"b")), ("exit", {"exit_code": 0})),
        )

        assert sandbox.run("x").stdout == "ab"
        assert server.bodies()[1]["stdout_offset"] == 1

    def test_command_timeout_error_is_fatal(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("error", {"error": "timed out", "error_type": "CommandTimeout"}),
            ),
        )

        with pytest.raises(CommandTimeoutError):
            sandbox.run("sleep 999")

    def test_read_offset_unavailable_is_fatal(self, server: Server, sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                (
                    "error",
                    {
                        "error": "offset 5 is gone",
                        "error_type": "ReadOffsetUnavailable",
                    },
                ),
            ),
        )

        with pytest.raises(SandboxOperationError, match="offset 5 is gone"):
            sandbox.run("x")

    def test_trailing_partial_character_is_not_swallowed(self, server: Server, sandbox):
        """A command whose last byte starts a character it never finishes."""
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"ab\xc3")),
                ("stream_end", {"stream": "stdout", "offset": 3}),
                ("exit", {"exit_code": 0}),
            ),
        )

        assert sandbox.run("x").stdout == "ab�"

    def test_acknowledgement_without_output_still_spends_the_budget(
        self, server: Server, sandbox
    ):
        """A resume that only re-acknowledges must not retry forever."""
        server.on(START_PATH, sse(started(), ("stdout", out(0, b"a"))))
        server.on(RESUME_PATH, sse(started()))

        with pytest.raises(SandboxConnectionError, match="without an exit|giving up"):
            sandbox.run("x")

        # Bounded by the retry budget rather than looping on the ack.
        assert len(server.requests) <= 2 + 5

    def test_gives_up_after_repeated_truncated_streams(self, server: Server, sandbox):
        server.on(START_PATH, sse(started(), ("stdout", out(0, b"a"))))
        server.on(RESUME_PATH, sse())

        with pytest.raises(SandboxConnectionError, match="without an exit|giving up"):
            sandbox.run("x")

    def test_409_conflict_surfaces_the_server_message(self, server: Server, sandbox):
        server.on(
            START_PATH,
            httpx.Response(
                409,
                json={
                    "detail": {
                        "error": "TransportMismatch",
                        "message": "stream it on the exec WebSocket",
                    }
                },
            ),
        )

        with pytest.raises(Exception, match="stream it on the exec WebSocket"):
            sandbox.run("x")


class TestUnsupportedOptions:
    @pytest.mark.parametrize(
        "kwargs", [{"pty": True}, {"close_input": False}, {"kill_on_disconnect": True}]
    )
    def test_rejected_with_a_pointer_to_the_websocket(self, sandbox, kwargs):
        with pytest.raises(ValueError, match="exec WebSocket"):
            sandbox.run("x", **kwargs)

    def test_kill_and_send_input_raise(self, server: Server, sandbox):
        server.on(START_PATH, sse(started(), ("exit", {"exit_code": 0})))

        handle = sandbox.run("x", wait=False)

        with pytest.raises(SandboxOperationError, match="one-way"):
            handle.kill()
        with pytest.raises(SandboxOperationError, match="stdin is closed"):
            handle.send_input("hi")


class TestReconnect:
    def test_resumes_at_the_given_offsets(self, server: Server, sandbox):
        server.on(
            RESUME_PATH,
            sse(started(), ("stdout", out(5, b"tail")), ("exit", {"exit_code": 0})),
        )

        handle = sandbox.reconnect("cmd-1", stdout_offset=5)

        assert handle.result.stdout == "tail"
        assert server.bodies()[0] == {
            "command_id": "cmd-1",
            "stdout_offset": 5,
            "stderr_offset": 0,
        }

    def test_missing_command_is_not_restarted(self, server: Server, sandbox):
        server.on(
            RESUME_PATH,
            httpx.Response(
                404, json={"detail": {"error": "CommandNotFound", "message": "gone"}}
            ),
        )

        with pytest.raises(SandboxOperationError, match="Command not found: cmd-1"):
            sandbox.reconnect("cmd-1").result

        assert [request.url.path for request in server.requests] == [RESUME_PATH]


class TestAsyncRun:
    @pytest.mark.asyncio
    async def test_streams_output_and_resumes(self, server: Server, async_sandbox):
        server.on(
            START_PATH,
            sse(
                started(),
                ("stdout", out(0, b"a")),
                ("ack_required", {"stdout_offset": 1, "stderr_offset": 0}),
            ),
        )
        server.on(
            RESUME_PATH,
            sse(started(), ("stdout", out(1, b"b")), ("exit", {"exit_code": 0})),
        )

        result = await async_sandbox.run("big")

        assert result.stdout == "ab"
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_handle_streams_chunks(self, server: Server, async_sandbox):
        server.on(
            START_PATH,
            sse(started(), ("stdout", out(0, b"hi")), ("exit", {"exit_code": 0})),
        )

        handle = await async_sandbox.run("x", wait=False)

        assert [chunk.data async for chunk in handle] == ["hi"]

    @pytest.mark.asyncio
    async def test_unsupported_option_rejected(self, async_sandbox):
        with pytest.raises(ValueError, match="exec WebSocket"):
            await async_sandbox.run("x", pty=True)


class TestTransportSelection:
    def test_missing_websockets_without_the_feature_raises(
        self, monkeypatch: pytest.MonkeyPatch, sandbox
    ):
        monkeypatch.delenv(_features.ENV_VAR, raising=False)
        monkeypatch.setattr("langsmith.sandbox._sandbox.WEBSOCKETS_AVAILABLE", False)

        with pytest.raises(ImportError) as excinfo:
            sandbox.run("x")

        assert "langsmith[sandbox]" in str(excinfo.value)
        assert "LANGSMITH_EXPERIMENTAL_FEATURES=sandbox_sse_exec" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_missing_websockets_without_the_feature_raises_async(
        self, monkeypatch: pytest.MonkeyPatch, async_sandbox
    ):
        monkeypatch.delenv(_features.ENV_VAR, raising=False)
        monkeypatch.setattr(
            "langsmith.sandbox._async_sandbox.WEBSOCKETS_AVAILABLE", False
        )

        with pytest.raises(ImportError, match="langsmith\\[sandbox\\]"):
            await async_sandbox.run("x")


class TestFeatureFlags:
    def test_off_by_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv(_features.ENV_VAR, raising=False)
        assert not _features.enabled(_features.SANDBOX_SSE_EXEC)

    @pytest.mark.parametrize(
        "value", ["sandbox_sse_exec", "sandbox-sse-exec", " SANDBOX_SSE_EXEC , "]
    )
    def test_enabled_by_name(self, monkeypatch: pytest.MonkeyPatch, value):
        monkeypatch.setenv(_features.ENV_VAR, value)
        assert _features.enabled(_features.SANDBOX_SSE_EXEC)

    def test_no_prefix_disables(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(_features.ENV_VAR, "sandbox_sse_exec,nosandbox_sse_exec")
        assert not _features.enabled(_features.SANDBOX_SSE_EXEC)

    def test_unknown_name_warns_and_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ):
        monkeypatch.setenv(_features.ENV_VAR, "not_a_feature,sandbox_sse_exec")

        assert _features.enabled(_features.SANDBOX_SSE_EXEC)
        assert "not_a_feature" in caplog.text
