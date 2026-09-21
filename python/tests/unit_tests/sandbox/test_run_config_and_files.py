"""Tests for run_config, stdin closing, and the filesystem search/range ops."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    RunConfig,
    SandboxClient,
    SandboxOperationError,
)
from langsmith.sandbox._models import CommandHandle
from langsmith.sandbox._sandbox import Sandbox
from langsmith.sandbox._ws_execute import _AsyncWSStreamControl, _WSStreamControl

from ._sse_fixtures import SSE_HEADERS, exited, sse_bytes, started

DATAPLANE = "https://sandbox-router.example.com/sb-123"


@pytest.fixture
def client():
    return SandboxClient(
        api_endpoint="http://test-server:8080", api_key="test-key", max_retries=0
    )


@pytest.fixture
def sandbox(client: SandboxClient):
    return Sandbox.from_dict(
        data={"name": "test-sandbox", "dataplane_url": DATAPLANE},
        client=client,
        auto_delete=False,
    )


class TestRunConfigModel:
    def test_to_payload_omits_unset(self):
        assert RunConfig(user="app").to_payload() == {"user": "app"}

    def test_to_payload_keeps_empty_env(self):
        assert RunConfig(env_vars={}).to_payload() == {"env_vars": {}}

    def test_from_dict_round_trip(self):
        parsed = RunConfig.from_dict(
            {"user": "1000:1000", "work_dir": "/workspace", "env_vars": {"A": "1"}}
        )
        assert parsed == RunConfig(
            user="1000:1000", work_dir="/workspace", env_vars={"A": "1"}
        )

    def test_snapshot_without_run_config_is_none(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "s",
                "status": "ready",
                "fs_capacity_bytes": 1,
            },
        )
        assert client.get_snapshot("snap-1").run_config is None

    def test_snapshot_parses_run_config(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "s",
                "status": "ready",
                "fs_capacity_bytes": 1,
                "run_config": {"user": "app", "work_dir": "/srv"},
            },
        )
        snapshot = client.get_snapshot("snap-1")
        assert snapshot.run_config == RunConfig(user="app", work_dir="/srv")


class TestRunConfigOnRequests:
    def test_create_sandbox_sends_run_config(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(
            url="http://test-server:8080/boxes",
            json={"name": "sb", "status": "ready", "dataplane_url": DATAPLANE},
        )
        client.create_sandbox("snap-1", run_config=RunConfig(user="app"))
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["run_config"] == {"user": "app"}

    def test_update_sandbox_sends_run_config(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(
            url="http://test-server:8080/boxes/sb",
            json={"name": "sb", "status": "ready"},
        )
        client.update_sandbox("sb", run_config={"env_vars": {"A": "1"}})
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["run_config"] == {"env_vars": {"A": "1"}}

    def test_update_without_run_config_omits_it(self, httpx_mock: HTTPXMock, client):
        httpx_mock.add_response(
            url="http://test-server:8080/boxes/sb",
            json={"name": "sb", "status": "ready"},
        )
        client.update_sandbox("sb", new_name="sb2")
        assert "run_config" not in json.loads(httpx_mock.get_requests()[0].content)

    def test_run_sends_run_config(self, httpx_mock: HTTPXMock, sandbox, monkeypatch):
        monkeypatch.setenv("LANGSMITH_EXPERIMENTAL_FEATURES", "sandbox_sse_exec")
        httpx_mock.add_response(
            url=f"{DATAPLANE}/execute/stream/start",
            content=sse_bytes(started(), exited()),
            headers=SSE_HEADERS,
        )
        sandbox.run("echo hi", run_config=RunConfig(user="app"))
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["run_config"] == {"user": "app"}

    @pytest.mark.parametrize("deprecated", [{"env": {"A": "1"}}, {"cwd": "/tmp"}])
    def test_run_config_with_deprecated_field_is_rejected(self, sandbox, deprecated):
        with pytest.raises(ValueError, match="deprecated env/cwd"):
            sandbox.run("echo hi", run_config=RunConfig(user="app"), **deprecated)

    def test_deprecated_fields_still_work_alone(
        self, httpx_mock: HTTPXMock, sandbox, monkeypatch
    ):
        monkeypatch.setenv("LANGSMITH_EXPERIMENTAL_FEATURES", "sandbox_sse_exec")
        httpx_mock.add_response(
            url=f"{DATAPLANE}/execute/stream/start",
            content=sse_bytes(started(), exited()),
            headers=SSE_HEADERS,
        )
        sandbox.run("echo hi", cwd="/tmp", env={"A": "1"})
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["cwd"] == "/tmp"
        assert body["env"] == {"A": "1"}
        assert "run_config" not in body


class TestCloseInput:
    def _handle(self, *, stdin_closed: bool, pty: bool = False) -> CommandHandle:
        handle = CommandHandle.__new__(CommandHandle)
        handle._control = MagicMock()
        handle._stdin_closed = stdin_closed
        handle._pty = pty
        return handle

    def test_send_input_raises_once_stdin_is_closed(self):
        handle = self._handle(stdin_closed=True)
        with pytest.raises(SandboxOperationError, match="close_input=False"):
            handle.send_input("data")
        handle._control.send_input.assert_not_called()

    def test_close_input_sends_the_message_once(self):
        handle = self._handle(stdin_closed=False)
        handle.close_input()
        handle.close_input()
        handle._control.send_close_stdin.assert_called_once_with()
        assert handle._stdin_closed is True

    def test_close_input_is_a_no_op_under_pty(self):
        handle = self._handle(stdin_closed=False, pty=True)
        handle.close_input()
        handle._control.send_close_stdin.assert_not_called()
        handle.send_input("\x04")
        handle._control.send_input.assert_called_once_with("\x04")

    def test_ws_payload_defaults_close_stdin_on(self, sandbox):
        with (
            patch("langsmith.sandbox._sandbox.CommandHandle"),
            patch(
                "langsmith.sandbox._ws_execute.run_ws_stream",
                return_value=(iter([]), MagicMock()),
            ) as mock_stream,
        ):
            sandbox.run("echo hi", wait=False)
        assert mock_stream.call_args.kwargs["close_stdin"] is True

    def test_ws_payload_omits_close_stdin_under_pty(self, sandbox):
        with (
            patch("langsmith.sandbox._sandbox.CommandHandle"),
            patch(
                "langsmith.sandbox._ws_execute.run_ws_stream",
                return_value=(iter([]), MagicMock()),
            ) as mock_stream,
        ):
            sandbox.run("echo hi", wait=False, pty=True)
        assert "close_stdin" not in mock_stream.call_args.kwargs

    def test_ws_payload_honours_opt_out(self, sandbox):
        with (
            patch("langsmith.sandbox._sandbox.CommandHandle"),
            patch(
                "langsmith.sandbox._ws_execute.run_ws_stream",
                return_value=(iter([]), MagicMock()),
            ) as mock_stream,
        ):
            sandbox.run("echo hi", wait=False, close_input=False)
        assert "close_stdin" not in mock_stream.call_args.kwargs


class TestFileSearch:
    def test_glob_request_and_response(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/glob",
            json={
                "matches": [
                    {
                        "path": "/workspace/app.py",
                        "is_dir": False,
                        "size_bytes": 12,
                        "modified_at": "2026-07-14T00:00:00Z",
                    }
                ],
                "truncated": True,
            },
        )
        result = sandbox.glob("**/*.py", "/workspace", limit=200)
        assert json.loads(httpx_mock.get_requests()[0].content) == {
            "pattern": "**/*.py",
            "path": "/workspace",
            "limit": 200,
        }
        assert result.truncated is True
        assert len(result) == 1
        assert [m.path for m in result] == ["/workspace/app.py"]
        assert result.matches[0].size_bytes == 12

    def test_ls_is_the_non_recursive_glob(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/glob", json={"matches": [], "truncated": False}
        )
        sandbox.ls("/workspace")
        assert json.loads(httpx_mock.get_requests()[0].content) == {
            "pattern": "*",
            "path": "/workspace",
        }

    def test_grep_request_and_response(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/grep",
            json={
                "matches": [{"path": "/w/app.py", "line": 12, "text": "# TODO"}],
                "truncated": False,
            },
        )
        result = sandbox.grep("TODO", "/w", glob="*.py")
        assert json.loads(httpx_mock.get_requests()[0].content) == {
            "pattern": "TODO",
            "path": "/w",
            "glob": "*.py",
        }
        assert result.matches[0].line == 12

    def test_missing_path_raises_not_found(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(url=f"{DATAPLANE}/glob", status_code=404, json={})
        with pytest.raises(Exception, match="not found"):
            sandbox.glob("*", "/nope")


class TestRangeRead:
    def test_partial_response(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=206,
            content=b"0123",
            headers={
                "Content-Range": "bytes 10-13/100",
                "ETag": '"abc"',
            },
        )
        chunk = sandbox.read_range("/big.bin", start=10, end=13)
        assert httpx_mock.get_requests()[0].headers["Range"] == "bytes=10-13"
        assert chunk.content == b"0123"
        assert (chunk.start, chunk.end, chunk.total_bytes) == (10, 14, 100)
        assert chunk.partial is True
        assert chunk.etag == '"abc"'

    def test_stale_if_range_reports_a_full_body(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=200,
            content=b"whole",
            headers={"ETag": '"new"'},
        )
        chunk = sandbox.read_range("/big.bin", start=10, if_range='"old"')
        assert httpx_mock.get_requests()[0].headers["If-Range"] == '"old"'
        assert chunk.partial is False
        assert (chunk.start, chunk.total_bytes) == (0, 5)

    def test_unchanged_file(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=304,
            headers={"ETag": '"same"'},
        )
        chunk = sandbox.read_range("/big.bin", start=0, if_none_match='"same"')
        assert chunk.unchanged is True
        assert chunk.content == b""

    def test_range_past_eof_is_an_error(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=416,
            content=b"invalid range",
            headers={"Content-Range": "bytes */100"},
        )
        with pytest.raises(SandboxOperationError, match="past the end"):
            sandbox.read_range("/big.bin", start=500)

    def test_suffix_range(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=206,
            content=b"tail",
            headers={"Content-Range": "bytes 96-99/100"},
        )
        sandbox.read_range("/big.bin", suffix_bytes=4)
        assert httpx_mock.get_requests()[0].headers["Range"] == "bytes=-4"

    def test_open_ended_range(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            status_code=206,
            content=b"rest",
            headers={"Content-Range": "bytes 96-99/100"},
        )
        sandbox.read_range("/big.bin", start=96)
        assert httpx_mock.get_requests()[0].headers["Range"] == "bytes=96-"

    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"start": 1, "suffix_bytes": 2}, {"start": 5, "end": 1}, {"start": -1}],
    )
    def test_invalid_ranges_rejected_before_the_request(self, sandbox, kwargs):
        with pytest.raises(ValueError):
            sandbox.read_range("/big.bin", **kwargs)

    def test_stat_reads_headers(self, httpx_mock: HTTPXMock, sandbox):
        httpx_mock.add_response(
            url=f"{DATAPLANE}/download?path=%2Fbig.bin",
            method="HEAD",
            headers={
                "Content-Length": "100",
                "ETag": '"abc"',
                "Last-Modified": "Mon, 17 Aug 2026 00:00:00 GMT",
                "Content-Type": "application/octet-stream",
            },
        )
        stat = sandbox.stat("/big.bin")
        assert stat.size_bytes == 100
        assert stat.etag == '"abc"'
        assert stat.content_type == "application/octet-stream"


class TestCloseInputBeforeBind:
    """A reconnected stream binds its socket only once iteration starts."""

    def test_close_before_bind_is_queued_then_sent(self):
        control = _WSStreamControl()
        control.send_close_stdin()
        assert control._close_stdin_pending is True

        ws = MagicMock()
        control._bind(ws)
        ws.send.assert_called_once_with(json.dumps({"type": "close_stdin"}))
        assert control._close_stdin_pending is False

    def test_close_after_bind_sends_immediately(self):
        control = _WSStreamControl()
        ws = MagicMock()
        control._bind(ws)
        control.send_close_stdin()
        ws.send.assert_called_once_with(json.dumps({"type": "close_stdin"}))

    def test_close_on_a_finished_stream_is_dropped(self):
        control = _WSStreamControl()
        control._unbind()
        control.send_close_stdin()
        assert control._close_stdin_pending is False

    @pytest.mark.asyncio
    async def test_async_close_before_bind_is_queued_then_flushed(self):
        control = _AsyncWSStreamControl()
        await control.send_close_stdin()
        assert control._close_stdin_pending is True

        ws = MagicMock()
        ws.send = AsyncMock()
        control._bind(ws)
        await control._flush_pending()
        ws.send.assert_awaited_once_with(json.dumps({"type": "close_stdin"}))


class TestReconnectPreservesIdentity:
    """A reconnected handle keeps the stdin and PTY state of the original."""

    def _handle(self, *, stdin_closed: bool, pty: bool) -> CommandHandle:
        handle = CommandHandle.__new__(CommandHandle)
        handle._command_id = "cmd-1"
        handle._sandbox = MagicMock()
        handle._control = MagicMock()
        handle._stdin_closed = stdin_closed
        handle._pty = pty
        handle._last_stdout_offset = 4
        handle._last_stderr_offset = 0
        return handle

    def test_reconnect_forwards_stdin_and_pty(self):
        handle = self._handle(stdin_closed=True, pty=True)
        handle.reconnect()
        handle._sandbox.reconnect.assert_called_once_with(
            "cmd-1",
            stdout_offset=4,
            stderr_offset=0,
            stdin_closed=True,
            pty=True,
        )

    def test_handle_built_by_reconnect_keeps_pty(self):
        handle = CommandHandle.__new__(CommandHandle)
        handle._control = MagicMock()
        handle._stdin_closed = False
        handle._pty = True
        # Under a PTY the close is a no-op, so the documented EOT path keeps working.
        handle.close_input()
        handle._control.send_close_stdin.assert_not_called()
        handle.send_input("\x04")
        handle._control.send_input.assert_called_once_with("\x04")
