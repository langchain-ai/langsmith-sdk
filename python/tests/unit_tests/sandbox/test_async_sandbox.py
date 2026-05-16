"""Tests for AsyncSandbox class."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from langsmith import Client
from langsmith.run_helpers import get_tracing_context, tracing_context
from langsmith.sandbox import (
    AsyncSandboxClient,
    AsyncServiceURL,
    DataplaneNotConfiguredError,
    ExecutionResult,
    ResourceNotFoundError,
    SandboxConnectionError,
    SandboxNotReadyError,
)
from langsmith.sandbox._async_sandbox import AsyncSandbox
from tests.unit_tests.conftest import parse_request_data


def _get_trace_client() -> Client:
    """Create a LangSmith client with mocked transport for tracing assertions."""
    return Client(session=MagicMock(), api_key="test", auto_batch_tracing=False)


def _trace_payloads(trace_client: Client) -> list[dict]:
    """Return parsed LangSmith trace request payloads from a mocked client."""
    payloads = []
    for call in trace_client.session.request.mock_calls:  # type: ignore[union-attr]
        if not call.args or call.args[0] not in {"POST", "PATCH"}:
            continue
        data = parse_request_data(call.kwargs["data"])
        for key in ("post", "patch"):
            payloads.extend(data.get(key) or [])
        if data.get("name"):
            payloads.append(data)
    return payloads


def _trace_payload(trace_client: Client, name: str) -> dict:
    """Return the first trace payload with the given run name."""
    return next(p for p in _trace_payloads(trace_client) if p.get("name") == name)


@pytest.fixture
async def client():
    """Create an AsyncSandboxClient with retries disabled for test isolation."""
    async with AsyncSandboxClient(
        api_endpoint="http://test-server:8080", max_retries=0
    ) as c:
        yield c


@pytest.fixture
def sandbox(client: AsyncSandboxClient):
    """Create an AsyncSandbox instance."""
    return AsyncSandbox.from_dict(
        data={
            "name": "test-sandbox",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=client,
        auto_delete=False,
    )


class TestAsyncSandboxProperties:
    """Tests for AsyncSandbox properties."""

    def test_name_property(self, sandbox):
        """Test name property."""
        assert sandbox.name == "test-sandbox"

    def test_dataplane_url_property(self, sandbox):
        """Test dataplane_url property."""
        assert sandbox.dataplane_url == "https://sandbox-router.example.com/sb-123"


class TestAsyncSandboxRetentionFields:
    """Tests for the two-stage retention fields on AsyncSandbox."""

    def test_from_dict_with_retention(self, client):
        """from_dict parses idle_ttl_seconds, delete_after_stop_seconds,
        and stopped_at."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "idle_ttl_seconds": 600,
                "delete_after_stop_seconds": 86400,
                "stopped_at": "2026-03-24T12:00:00Z",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.idle_ttl_seconds == 600
        assert sb.delete_after_stop_seconds == 86400
        assert sb.stopped_at == "2026-03-24T12:00:00Z"

    def test_from_dict_without_retention(self, client):
        """Retention fields default to None when absent."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.idle_ttl_seconds is None
        assert sb.delete_after_stop_seconds is None
        assert sb.stopped_at is None

    def test_from_dict_with_zero_retention(self, client):
        """Zero values are preserved (each disables that retention stage)."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "idle_ttl_seconds": 0,
                "delete_after_stop_seconds": 0,
                "stopped_at": None,
            },
            client=client,
            auto_delete=False,
        )
        assert sb.idle_ttl_seconds == 0
        assert sb.delete_after_stop_seconds == 0
        assert sb.stopped_at is None

    def test_from_dict_silently_ignores_legacy_fields(self, client):
        """Older smith-go responses may include the now-removed
        ttl_seconds/expires_at fields; the SDK should silently drop them."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "ttl_seconds": 3600,
                "expires_at": "2026-03-24T12:00:00Z",
                "idle_ttl_seconds": 600,
            },
            client=client,
            auto_delete=False,
        )
        assert sb.idle_ttl_seconds == 600
        assert sb.delete_after_stop_seconds is None
        assert sb.stopped_at is None
        assert not hasattr(sb, "ttl_seconds")
        assert not hasattr(sb, "expires_at")


class TestAsyncSandboxStatusFields:
    """Tests for status fields on AsyncSandbox."""

    def test_from_dict_with_status(self, client):
        """Test from_dict parses status fields."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "status_message": None,
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.status == "provisioning"
        assert sb.status_message is None

    def test_from_dict_defaults_to_ready(self, client):
        """Test from_dict defaults status to 'ready' when absent."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.status == "ready"
        assert sb.status_message is None

    async def test_provisioning_sandbox_blocks_run(self, client):
        """Test that run() raises SandboxNotReadyError for non-ready sandbox."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError, match="not ready"):
            await sb.run("echo hello")

    async def test_provisioning_sandbox_blocks_write(self, client):
        """Test that write() raises SandboxNotReadyError for non-ready sandbox."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError):
            await sb.write("/tmp/test.txt", "hello")

    async def test_provisioning_sandbox_blocks_read(self, client):
        """Test that read() raises SandboxNotReadyError for non-ready sandbox."""
        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError):
            await sb.read("/tmp/test.txt")


class TestAsyncSandboxRun:
    """Tests for async sandbox run command."""

    async def test_run_command_success(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a successful command."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={
                "stdout": "hello world\n",
                "stderr": "",
                "exit_code": 0,
            },
        )

        result = await sandbox.run("echo hello world")

        assert result.stdout == "hello world\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.success is True

    async def test_run_command_failure(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a failing command."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={
                "stdout": "",
                "stderr": "command not found\n",
                "exit_code": 127,
            },
        )

        result = await sandbox.run("nonexistent-command")

        assert result.exit_code == 127
        assert result.success is False

    async def test_run_connection_error(self, sandbox, httpx_mock: HTTPXMock):
        """Test run with connection error."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            await sandbox.run("echo hello")

    async def test_run_without_dataplane_url(self, client: AsyncSandboxClient):
        """Test run raises error when dataplane_url is not configured."""
        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            await sandbox.run("echo hello")

        assert "test-sandbox" in str(exc_info.value)
        assert "dataplane_url" in str(exc_info.value)

    async def test_run_with_env(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with environment variables."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        await sandbox.run("echo $MY_VAR", env={"MY_VAR": "hello", "OTHER": "value"})

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["env"] == {"MY_VAR": "hello", "OTHER": "value"}

    async def test_run_traces_invocation_with_sandbox_metadata(
        self, client, monkeypatch
    ):
        """Test that run() creates a trace with sandbox metadata in context."""
        trace_client = _get_trace_client()
        sandbox = AsyncSandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        observed = {}

        async def fake_run_ws(*args, **kwargs):
            observed["metadata"] = dict(get_tracing_context()["metadata"])
            return ExecutionResult(stdout="hello\n", stderr="", exit_code=0)

        monkeypatch.setattr(sandbox, "_run_ws", fake_run_ws)

        with tracing_context(
            enabled=True,
            client=trace_client,
            metadata={"sandbox_id": "outer", "sandbox_name": "outer"},
        ):
            result = await sandbox.run(
                "echo $SECRET", env={"SECRET": "redacted"}, cwd="/tmp"
            )

        assert result.stdout == "hello\n"
        assert observed["metadata"]["sandbox_id"] == "sandbox-123"
        payloads = _trace_payloads(trace_client)
        run_payload = next(p for p in payloads if p.get("name") == "Sandbox.run")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"]["cwd"] == "/tmp"
        assert "redacted" not in str(run_payload["inputs"])

    async def test_reconnect_traces_invocation_with_sandbox_metadata(
        self, client, monkeypatch
    ):
        """Test reconnect() traces sanitized dataplane inputs."""
        trace_client = _get_trace_client()
        sandbox = AsyncSandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

        async def empty_stream():
            if False:
                yield {}

        async def fake_reconnect_ws_stream(*args, **kwargs):
            return empty_stream(), None

        monkeypatch.setattr(
            "langsmith.sandbox._ws_execute.reconnect_ws_stream_async",
            fake_reconnect_ws_stream,
        )

        with tracing_context(
            enabled=True,
            client=trace_client,
            metadata={"sandbox_id": "outer", "sandbox_name": "outer"},
        ):
            handle = await sandbox.reconnect(
                "cmd-123", stdout_offset=7, stderr_offset=11
            )

        assert handle.command_id == "cmd-123"
        run_payload = _trace_payload(trace_client, "Sandbox.reconnect")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"] == {
            "command_id": "cmd-123",
            "stdout_offset": 7,
            "stderr_offset": 11,
        }

    async def test_run_with_custom_headers(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with per-request headers."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        await sandbox.run(
            "echo hello",
            headers={
                "X-Api-Key": "override-key",
                "X-Test-Header": "sandbox-run",
            },
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Api-Key") == "override-key"
        assert request.headers.get("X-Test-Header") == "sandbox-run"

    async def test_run_with_cwd(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with custom working directory."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "/tmp\n", "stderr": "", "exit_code": 0},
        )

        await sandbox.run("pwd", cwd="/tmp")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["cwd"] == "/tmp"

    async def test_run_with_custom_shell(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with custom shell."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        await sandbox.run("echo hello", shell="/bin/sh")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["shell"] == "/bin/sh"

    async def test_run_default_shell(self, sandbox, httpx_mock: HTTPXMock):
        """Test that default shell is /bin/bash."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        await sandbox.run("echo hello")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["shell"] == "/bin/bash"

    async def test_run_omits_none_values(self, sandbox, httpx_mock: HTTPXMock):
        """Test that None values for env and cwd are omitted from payload."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        await sandbox.run("echo hello", env=None, cwd=None)

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "env" not in payload
        assert "cwd" not in payload


class TestAsyncSandboxWrite:
    """Tests for async sandbox file write."""

    async def test_write_text_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test writing a text file."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/upload?path=%2Fapp%2Ftest.txt",
            json={
                "path": "/app/test.txt",
                "written": 11,
            },
        )

        # Should not raise
        await sandbox.write("/app/test.txt", "hello world")

        # Verify request is multipart form
        request = httpx_mock.get_request()
        assert b"hello world" in request.content
        content_type = request.headers.get("content-type", "")
        assert content_type.startswith("multipart/form-data")

    async def test_write_binary_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test writing a binary file."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/upload?path=%2Fapp%2Fdata.bin",
            json={
                "path": "/app/data.bin",
                "written": 4,
            },
        )

        binary_data = b"\x00\x01\x02\x03"
        await sandbox.write("/app/data.bin", binary_data)

        # Verify request is multipart form with binary content
        request = httpx_mock.get_request()
        assert binary_data in request.content
        content_type = request.headers.get("content-type", "")
        assert content_type.startswith("multipart/form-data")

    async def test_write_with_custom_headers(self, sandbox, httpx_mock: HTTPXMock):
        """Test writing a file with per-request headers."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/upload?path=%2Fapp%2Ftest.txt",
            json={"path": "/app/test.txt", "written": 5},
        )

        await sandbox.write(
            "/app/test.txt",
            "hello",
            headers={"X-Test-Header": "sandbox-write"},
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Test-Header") == "sandbox-write"

    async def test_write_without_dataplane_url(self, client: AsyncSandboxClient):
        """Test write raises error when dataplane_url is not configured."""
        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            await sandbox.write("/app/test.txt", "hello")

        assert "test-sandbox" in str(exc_info.value)

    async def test_write_traces_invocation_with_sandbox_metadata(
        self, client, httpx_mock: HTTPXMock
    ):
        """Test write() traces file metadata without file contents."""
        trace_client = _get_trace_client()
        sandbox = AsyncSandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/upload?path=%2Fapp%2Ftest.txt",
            json={"path": "/app/test.txt", "written": 6},
        )

        with tracing_context(enabled=True, client=trace_client):
            await sandbox.write("/app/test.txt", "secret", timeout=12)

        run_payload = _trace_payload(trace_client, "Sandbox.write")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"] == {
            "path": "/app/test.txt",
            "timeout": 12,
            "content_bytes": 6,
        }
        assert "secret" not in str(run_payload["inputs"])


class TestAsyncSandboxRead:
    """Tests for async sandbox file read."""

    async def test_read_text_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading a text file."""
        # URL uses query parameter with encoded path
        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Ftest.txt",
            content=b"hello world",
            headers={"Content-Type": "application/octet-stream"},
        )

        content = await sandbox.read("/app/test.txt")

        assert content == b"hello world"

    async def test_read_binary_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading a binary file."""
        binary_data = b"\x00\x01\x02\x03"

        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Fdata.bin",
            content=binary_data,
            headers={"Content-Type": "application/octet-stream"},
        )

        content = await sandbox.read("/app/data.bin")

        assert content == binary_data

    async def test_read_file_not_found(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading non-existent file."""
        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Fnonexistent.txt",
            json={"error": "NotFound", "message": "file not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            await sandbox.read("/app/nonexistent.txt")

    async def test_read_without_dataplane_url(self, client: AsyncSandboxClient):
        """Test read raises error when dataplane_url is not configured."""
        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            await sandbox.read("/app/test.txt")

        assert "test-sandbox" in str(exc_info.value)

    async def test_read_traces_invocation_with_sandbox_metadata(
        self, client, httpx_mock: HTTPXMock
    ):
        """Test read() traces path metadata without file contents in inputs."""
        trace_client = _get_trace_client()
        sandbox = AsyncSandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Ftest.txt",
            content=b"secret",
            headers={"Content-Type": "application/octet-stream"},
        )

        with tracing_context(enabled=True, client=trace_client):
            content = await sandbox.read("/app/test.txt", timeout=12)

        assert content == b"secret"
        run_payload = _trace_payload(trace_client, "Sandbox.read")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"] == {"path": "/app/test.txt", "timeout": 12}
        assert "secret" not in str(run_payload["inputs"])


class TestAsyncSandboxTunnel:
    """Tests for async sandbox TCP tunnels."""

    async def test_tunnel_traces_invocation_with_sandbox_metadata(
        self, client, monkeypatch
    ):
        """Test tunnel() traces dataplane tunnel parameters."""
        trace_client = _get_trace_client()
        sandbox = AsyncSandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

        monkeypatch.setattr("langsmith.sandbox._tunnel.Tunnel._start", lambda *a: None)

        with tracing_context(enabled=True, client=trace_client):
            tunnel = await sandbox.tunnel(
                5432,
                local_port=15432,
                max_reconnects=5,
            )

        assert tunnel.remote_port == 5432
        assert tunnel.local_port == 15432
        run_payload = _trace_payload(trace_client, "Sandbox.tunnel")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"] == {
            "remote_port": 5432,
            "local_port": 15432,
            "max_reconnects": 5,
        }


class TestAsyncSandboxContextManager:
    """Tests for async sandbox context manager."""

    async def test_auto_delete_on_exit(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox is deleted on async context exit."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=True,
        )

        async with sandbox:
            pass

        # Verify delete was called
        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "DELETE"

    async def test_no_delete_when_auto_delete_false(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox is not deleted when auto_delete is False."""
        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=False,
        )

        async with sandbox:
            pass

        # Verify no delete request
        requests = httpx_mock.get_requests()
        assert len(requests) == 0


class TestAsyncSandboxService:
    """Tests for AsyncSandbox.service() convenience method."""

    async def test_service_delegates_to_client(self, client: AsyncSandboxClient):
        """Test service() calls client.service() with sandbox name."""
        mock_svc = AsyncServiceURL(
            browser_url="http://b",
            service_url="http://s/",
            token="t",
            expires_at="2026-04-01T12:10:00Z",
        )
        client.service = AsyncMock(return_value=mock_svc)  # type: ignore[method-assign]

        sb = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

        result = await sb.service(port=3000, expires_in_seconds=1800)

        client.service.assert_called_once_with(
            "test-sandbox", 3000, expires_in_seconds=1800, headers=None
        )
        assert result is mock_svc
