"""Tests for AsyncSandbox class."""

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    AsyncSandboxClient,
    DataplaneNotConfiguredError,
    ResourceNotFoundError,
    SandboxConnectionError,
)
from langsmith.sandbox._async_sandbox import AsyncSandbox


@pytest.fixture
async def client():
    """Create an AsyncSandboxClient."""
    async with AsyncSandboxClient(api_endpoint="http://test-server:8080") as c:
        yield c


@pytest.fixture
def sandbox(client: AsyncSandboxClient):
    """Create an AsyncSandbox instance."""
    return AsyncSandbox.from_dict(
        data={
            "name": "test-sandbox",
            "template_name": "test-template",
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

    def test_template_name_property(self, sandbox):
        """Test template_name property."""
        assert sandbox.template_name == "test-template"

    def test_dataplane_url_property(self, sandbox):
        """Test dataplane_url property."""
        assert sandbox.dataplane_url == "https://sandbox-router.example.com/sb-123"


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
                "template_name": "test-template",
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

    async def test_write_without_dataplane_url(self, client: AsyncSandboxClient):
        """Test write raises error when dataplane_url is not configured."""
        sandbox = AsyncSandbox.from_dict(
            data={
                "name": "test-sandbox",
                "template_name": "test-template",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            await sandbox.write("/app/test.txt", "hello")

        assert "test-sandbox" in str(exc_info.value)


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
                "template_name": "test-template",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError) as exc_info:
            await sandbox.read("/app/test.txt")

        assert "test-sandbox" in str(exc_info.value)


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
                "template_name": "test-template",
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
                "template_name": "test-template",
            },
            client=client,
            auto_delete=False,
        )

        async with sandbox:
            pass

        # Verify no delete request
        requests = httpx_mock.get_requests()
        assert len(requests) == 0
