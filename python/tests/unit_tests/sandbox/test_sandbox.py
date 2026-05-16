"""Tests for Sandbox class."""

from unittest.mock import MagicMock

import pytest
from pytest_httpx import HTTPXMock

from langsmith import Client
from langsmith.run_helpers import get_tracing_context, tracing_context
from langsmith.sandbox import (
    DataplaneNotConfiguredError,
    ExecutionResult,
    ResourceNotFoundError,
    SandboxClient,
    SandboxConnectionError,
    SandboxNotReadyError,
    ServiceURL,
)
from langsmith.sandbox._sandbox import Sandbox
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


@pytest.fixture
def client():
    """Create a SandboxClient with retries disabled for test isolation."""
    return SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)


@pytest.fixture
def sandbox(client: SandboxClient):
    """Create a Sandbox instance."""
    return Sandbox.from_dict(
        data={
            "name": "test-sandbox",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=client,
        auto_delete=False,
    )


class TestSandboxProperties:
    """Tests for Sandbox properties."""

    def test_name_property(self, sandbox):
        """Test name property."""
        assert sandbox.name == "test-sandbox"

    def test_dataplane_url_property(self, sandbox):
        """Test dataplane_url property."""
        assert sandbox.dataplane_url == "https://sandbox-router.example.com/sb-123"


class TestSandboxRetentionFields:
    """Tests for the two-stage retention fields on Sandbox."""

    def test_from_dict_with_retention(self, client):
        """from_dict parses idle_ttl_seconds, delete_after_stop_seconds,
        and stopped_at."""
        sb = Sandbox.from_dict(
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
        sb = Sandbox.from_dict(
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
        sb = Sandbox.from_dict(
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
        ttl_seconds/expires_at fields; the SDK should silently drop them
        rather than fail."""
        sb = Sandbox.from_dict(
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


class TestSandboxStatusFields:
    """Tests for status fields on Sandbox."""

    def test_from_dict_with_status(self, client):
        """Test from_dict parses status fields."""
        sb = Sandbox.from_dict(
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

    def test_from_dict_failed_status(self, client):
        """Test from_dict parses failed status with message."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "failed",
                "status_message": "No capacity available",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.status == "failed"
        assert sb.status_message == "No capacity available"

    def test_from_dict_defaults_to_ready(self, client):
        """Test from_dict defaults status to 'ready' when absent."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=False,
        )
        assert sb.status == "ready"
        assert sb.status_message is None

    def test_provisioning_sandbox_blocks_run(self, client):
        """Test that run() raises SandboxNotReadyError for non-ready sandbox."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError, match="not ready"):
            sb.run("echo hello")

    def test_failed_sandbox_blocks_run(self, client):
        """Test that run() raises SandboxNotReadyError for failed sandbox."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "failed",
                "status_message": "No capacity",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError):
            sb.run("echo hello")

    def test_provisioning_sandbox_blocks_write(self, client):
        """Test that write() raises SandboxNotReadyError for non-ready sandbox."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError):
            sb.write("/tmp/test.txt", "hello")

    def test_provisioning_sandbox_blocks_read(self, client):
        """Test that read() raises SandboxNotReadyError for non-ready sandbox."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "status": "provisioning",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        with pytest.raises(SandboxNotReadyError):
            sb.read("/tmp/test.txt")


class TestSandboxRun:
    """Tests for sandbox run command."""

    def test_run_command_success(self, sandbox, httpx_mock: HTTPXMock):
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

        result = sandbox.run("echo hello world")

        assert result.stdout == "hello world\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.success is True

    def test_run_command_failure(self, sandbox, httpx_mock: HTTPXMock):
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

        result = sandbox.run("nonexistent-command")

        assert result.exit_code == 127
        assert result.success is False

    def test_run_connection_error(self, sandbox, httpx_mock: HTTPXMock):
        """Test run with connection error."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            sandbox.run("echo hello")

    def test_run_without_dataplane_url(self, client: SandboxClient):
        """Test run raises error when dataplane_url is not configured."""
        sandbox = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            sandbox.run("echo hello")

        assert "test-sandbox" in str(exc_info.value)
        assert "dataplane_url" in str(exc_info.value)

    def test_run_with_env(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with environment variables."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo $MY_VAR", env={"MY_VAR": "hello", "OTHER": "value"})

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["env"] == {"MY_VAR": "hello", "OTHER": "value"}

    def test_run_injects_langsmith_sandbox_id_env(self, client, httpx_mock: HTTPXMock):
        """Test that command env includes the LangSmith sandbox ID."""
        import json

        sandbox = Sandbox.from_dict(
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
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo hello")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["env"]["LANGSMITH_SANDBOX_ID"] == "sandbox-123"

    def test_run_preserves_env_when_injecting_sandbox_id(
        self, client, httpx_mock: HTTPXMock
    ):
        """Test that sandbox ID env injection preserves user env vars."""
        import json

        sandbox = Sandbox.from_dict(
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
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo hello", env={"MY_VAR": "hello"})

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["env"] == {
            "MY_VAR": "hello",
            "LANGSMITH_SANDBOX_ID": "sandbox-123",
        }

    def test_run_traces_invocation_with_sandbox_metadata(self, client, monkeypatch):
        """Test that run() creates a trace with sandbox metadata in context."""
        trace_client = _get_trace_client()
        sandbox = Sandbox.from_dict(
            data={
                "id": "sandbox-123",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )
        observed = {}

        def fake_run_untraced(*args, **kwargs):
            observed["metadata"] = dict(get_tracing_context()["metadata"])
            return ExecutionResult(stdout="hello\n", stderr="", exit_code=0)

        monkeypatch.setattr(sandbox, "_run_untraced", fake_run_untraced)

        with tracing_context(
            enabled=True,
            client=trace_client,
            metadata={"sandbox_id": "outer", "sandbox_name": "outer"},
        ):
            result = sandbox.run("echo $SECRET", env={"SECRET": "redacted"}, cwd="/tmp")

        assert result.stdout == "hello\n"
        assert observed["metadata"]["sandbox_id"] == "sandbox-123"
        payloads = _trace_payloads(trace_client)
        run_payload = next(p for p in payloads if p.get("name") == "Sandbox.run")
        assert run_payload["run_type"] == "tool"
        assert run_payload["extra"]["metadata"]["sandbox_id"] == "sandbox-123"
        assert run_payload["extra"]["metadata"]["sandbox_name"] == "test-sandbox"
        assert run_payload["inputs"]["env_keys"] == ["SECRET"]
        assert run_payload["inputs"]["cwd"] == "/tmp"
        assert "redacted" not in str(run_payload["inputs"])

    def test_run_with_custom_headers(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with per-request headers."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "hello\n", "stderr": "", "exit_code": 0},
        )

        sandbox.run(
            "echo hello",
            headers={
                "X-Api-Key": "override-key",
                "X-Test-Header": "sandbox-run",
            },
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Api-Key") == "override-key"
        assert request.headers.get("X-Test-Header") == "sandbox-run"

    def test_run_with_cwd(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with custom working directory."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "/tmp\n", "stderr": "", "exit_code": 0},
        )

        sandbox.run("pwd", cwd="/tmp")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["cwd"] == "/tmp"

    def test_run_with_custom_shell(self, sandbox, httpx_mock: HTTPXMock):
        """Test running a command with custom shell."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo hello", shell="/bin/sh")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["shell"] == "/bin/sh"

    def test_run_default_shell(self, sandbox, httpx_mock: HTTPXMock):
        """Test that default shell is /bin/bash."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo hello")

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["shell"] == "/bin/bash"

    def test_run_omits_none_values(self, sandbox, httpx_mock: HTTPXMock):
        """Test that None values for env and cwd are omitted from payload."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        sandbox.run("echo hello", env=None, cwd=None)

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "env" not in payload
        assert "cwd" not in payload


class TestSandboxWrite:
    """Tests for sandbox file write."""

    def test_write_text_file(self, sandbox, httpx_mock: HTTPXMock):
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
        sandbox.write("/app/test.txt", "hello world")

        # Verify request is multipart form
        request = httpx_mock.get_request()
        assert b"hello world" in request.content
        content_type = request.headers.get("content-type", "")
        assert content_type.startswith("multipart/form-data")

    def test_write_binary_file(self, sandbox, httpx_mock: HTTPXMock):
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
        sandbox.write("/app/data.bin", binary_data)

        # Verify request is multipart form with binary content
        request = httpx_mock.get_request()
        assert binary_data in request.content
        content_type = request.headers.get("content-type", "")
        assert content_type.startswith("multipart/form-data")

    def test_write_with_custom_headers(self, sandbox, httpx_mock: HTTPXMock):
        """Test writing a file with per-request headers."""
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/upload?path=%2Fapp%2Ftest.txt",
            json={"path": "/app/test.txt", "written": 5},
        )

        sandbox.write(
            "/app/test.txt",
            "hello",
            headers={"X-Test-Header": "sandbox-write"},
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Test-Header") == "sandbox-write"

    def test_write_without_dataplane_url(self, client: SandboxClient):
        """Test write raises error when dataplane_url is not configured."""
        sandbox = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            sandbox.write("/app/test.txt", "hello")

        assert "test-sandbox" in str(exc_info.value)


class TestSandboxRead:
    """Tests for sandbox file read."""

    def test_read_text_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading a text file."""
        # URL uses query parameter with encoded path
        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Ftest.txt",
            content=b"hello world",
            headers={"Content-Type": "application/octet-stream"},
        )

        content = sandbox.read("/app/test.txt")

        assert content == b"hello world"

    def test_read_binary_file(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading a binary file."""
        binary_data = b"\x00\x01\x02\x03"

        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Fdata.bin",
            content=binary_data,
            headers={"Content-Type": "application/octet-stream"},
        )

        content = sandbox.read("/app/data.bin")

        assert content == binary_data

    def test_read_file_not_found(self, sandbox, httpx_mock: HTTPXMock):
        """Test reading non-existent file."""
        httpx_mock.add_response(
            method="GET",
            url="https://sandbox-router.example.com/sb-123/download?path=%2Fapp%2Fnonexistent.txt",
            json={"error": "NotFound", "message": "file not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            sandbox.read("/app/nonexistent.txt")

    def test_read_without_dataplane_url(self, client: SandboxClient):
        """Test read raises error when dataplane_url is not configured."""
        sandbox = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            sandbox.read("/app/test.txt")

        assert "test-sandbox" in str(exc_info.value)


class TestSandboxContextManager:
    """Tests for sandbox context manager."""

    def test_auto_delete_on_exit(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test sandbox is deleted on context exit."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        sandbox = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=True,
        )

        with sandbox:
            pass

        # Verify delete was called
        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "DELETE"

    def test_no_delete_when_auto_delete_false(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox is not deleted when auto_delete is False."""
        sandbox = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
            },
            client=client,
            auto_delete=False,
        )

        with sandbox:
            pass

        # Verify no delete request
        requests = httpx_mock.get_requests()
        assert len(requests) == 0


class TestSandboxService:
    """Tests for Sandbox.service() convenience method."""

    def test_service_delegates_to_client(self, client: SandboxClient):
        """Test service() calls client.service() with sandbox name."""
        mock_svc = ServiceURL(
            browser_url="http://b",
            service_url="http://s/",
            token="t",
            expires_at="2026-04-01T12:10:00Z",
        )
        client.service = MagicMock(return_value=mock_svc)  # type: ignore[method-assign]

        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            client=client,
            auto_delete=False,
        )

        result = sb.service(port=3000, expires_in_seconds=1800)

        client.service.assert_called_once_with(
            "test-sandbox", 3000, expires_in_seconds=1800, headers=None
        )
        assert result is mock_svc
