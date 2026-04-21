"""Tests for AsyncSandboxClient."""

from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    AsyncSandboxClient,
    AsyncServiceURL,
    ResourceCreationError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceStatus,
    ResourceTimeoutError,
    SandboxConnectionError,
)


@pytest.fixture
async def client():
    """Create an AsyncSandboxClient with retries disabled for test isolation."""
    async with AsyncSandboxClient(
        api_endpoint="http://test-server:8080", max_retries=0
    ) as c:
        yield c


class TestAsyncSandboxClientInit:
    """Tests for async client initialization."""

    async def test_creates_with_endpoint(self):
        """Test client creation with endpoint."""
        client = AsyncSandboxClient(api_endpoint="http://localhost:8080")
        assert client._base_url == "http://localhost:8080"
        await client.aclose()

    async def test_strips_trailing_slash(self):
        """Test trailing slash is stripped."""
        client = AsyncSandboxClient(api_endpoint="http://localhost:8080/")
        assert client._base_url == "http://localhost:8080"
        await client.aclose()

    async def test_async_context_manager(self):
        """Test async context manager usage."""
        async with AsyncSandboxClient(api_endpoint="http://localhost:8080") as client:
            assert client._base_url == "http://localhost:8080"

    async def test_derives_endpoint_from_langsmith_endpoint(self):
        """Test endpoint derivation from LANGSMITH_ENDPOINT."""
        with patch(
            "langsmith.sandbox._async_client._get_default_api_endpoint",
            return_value="https://custom.langsmith.com/v2/sandboxes",
        ):
            client = AsyncSandboxClient()
            assert client._base_url == "https://custom.langsmith.com/v2/sandboxes"
            await client.aclose()

    async def test_explicit_endpoint_overrides_env(self):
        """Test explicit endpoint overrides environment variable."""
        with patch(
            "langsmith.sandbox._async_client._get_default_api_endpoint",
            return_value="https://env.langsmith.com/v2/sandboxes",
        ):
            client = AsyncSandboxClient(api_endpoint="http://explicit:8080")
            assert client._base_url == "http://explicit:8080"
            await client.aclose()

    async def test_api_key_from_parameter(self):
        """Test API key from parameter."""
        client = AsyncSandboxClient(
            api_endpoint="http://localhost:8080",
            api_key="test-key",
        )
        assert client._http.headers.get("X-Api-Key") == "test-key"
        await client.aclose()

    async def test_api_key_from_environment(self):
        """Test API key from environment variable."""
        with patch(
            "langsmith.sandbox._async_client._get_default_api_key",
            return_value="env-key",
        ):
            client = AsyncSandboxClient(api_endpoint="http://localhost:8080")
            assert client._http.headers.get("X-Api-Key") == "env-key"
            await client.aclose()

    async def test_explicit_api_key_overrides_env(self):
        """Test explicit API key overrides environment variable."""
        with patch(
            "langsmith.sandbox._async_client._get_default_api_key",
            return_value="env-key",
        ):
            client = AsyncSandboxClient(
                api_endpoint="http://localhost:8080",
                api_key="explicit-key",
            )
            assert client._http.headers.get("X-Api-Key") == "explicit-key"
            await client.aclose()

    async def test_max_retries_default(self):
        """Test default max_retries is 3."""
        from langsmith.sandbox._transport import AsyncRetryTransport

        client = AsyncSandboxClient(api_endpoint="http://localhost:8080")
        transport = client._http._transport
        assert isinstance(transport, AsyncRetryTransport)
        assert transport._max_retries == 3
        await client.aclose()

    async def test_max_retries_custom(self):
        """Test custom max_retries value."""
        from langsmith.sandbox._transport import AsyncRetryTransport

        client = AsyncSandboxClient(api_endpoint="http://localhost:8080", max_retries=5)
        transport = client._http._transport
        assert isinstance(transport, AsyncRetryTransport)
        assert transport._max_retries == 5
        await client.aclose()

    async def test_max_retries_zero_disables(self):
        """Test max_retries=0 disables retries."""
        from langsmith.sandbox._transport import AsyncRetryTransport

        client = AsyncSandboxClient(api_endpoint="http://localhost:8080", max_retries=0)
        transport = client._http._transport
        assert isinstance(transport, AsyncRetryTransport)
        assert transport._max_retries == 0
        await client.aclose()


class TestAsyncSandboxOperations:
    """Tests for async sandbox operations."""

    async def test_create_sandbox(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(snapshot_id="snap-1")

        assert sandbox.name == "test-sandbox"
        assert sandbox.id == "550e8400-e29b-41d4-a716-446655440003"
        assert (
            sandbox.dataplane_url == "https://sandbox-router.example.com/tenant/sb-123"
        )

    async def test_create_sandbox_forwards_proxy_config(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """proxy_config should appear verbatim in the POST body."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
            },
            status_code=201,
        )

        proxy_config = {
            "access_control": {"allow_list": ["github.com", "*.example.com"]},
        }
        await client.create_sandbox(
            snapshot_id="snap-1",
            proxy_config=proxy_config,
        )

        body = json.loads(httpx_mock.get_request().content)
        assert body["proxy_config"] == proxy_config

    async def test_create_sandbox_omits_proxy_config_when_none(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """proxy_config must not appear in the payload when not provided."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
            },
            status_code=201,
        )

        await client.create_sandbox(snapshot_id="snap-1")
        body = json.loads(httpx_mock.get_request().content)
        assert "proxy_config" not in body

    async def test_create_sandbox_merges_custom_headers(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test per-request headers override default client headers."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        await client.create_sandbox(
            snapshot_id="snap-1",
            headers={
                "X-Api-Key": "override-key",
                "X-Test-Header": "sandbox-client",
            },
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Api-Key") == "override-key"
        assert request.headers.get("X-Test-Header") == "sandbox-client"

    async def test_sandbox_async_context_manager(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox with async context manager."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
            },
            status_code=201,
        )
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        async with await client.sandbox(snapshot_id="snap-1") as sandbox:
            assert sandbox.name == "test-sandbox"

        # Verify delete was called
        requests = httpx_mock.get_requests()
        assert any(r.method == "DELETE" for r in requests)

    async def test_sandbox_timeout(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox creation timeout."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={"detail": "Timeout waiting for sandbox to be ready"},
            status_code=408,
        )

        with pytest.raises(ResourceTimeoutError):
            await client.create_sandbox(snapshot_id="snap-1")

    async def test_list_sandboxes(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test listing sandboxes."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes",
            json={
                "sandboxes": [
                    {
                        "name": "sandbox-1",
                    },
                ]
            },
        )

        sandboxes = await client.list_sandboxes()

        assert len(sandboxes) == 1
        assert sandboxes[0].name == "sandbox-1"

    async def test_delete_sandbox(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test deleting a sandbox."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        # Should not raise
        await client.delete_sandbox("test-sandbox")

    async def test_update_sandbox(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a sandbox's name."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "my-sandbox-renamed",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.update_sandbox(
            "my-sandbox", new_name="my-sandbox-renamed"
        )

        assert sandbox.name == "my-sandbox-renamed"
        assert sandbox.id == "550e8400-e29b-41d4-a716-446655440003"

    async def test_update_sandbox_not_found(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a non-existent sandbox."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/nonexistent",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            await client.update_sandbox("nonexistent", new_name="new-name")

    async def test_update_sandbox_name_conflict(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating sandbox to a name that already exists."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={"detail": {"error": "Conflict", "message": "Name already in use"}},
            status_code=409,
        )

        with pytest.raises(ResourceNameConflictError) as exc_info:
            await client.update_sandbox("my-sandbox", new_name="existing-sandbox")

        assert exc_info.value.resource_type == "sandbox"

    async def test_create_sandbox_async_returns_provisioning(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test async sandbox creation returns provisioning status."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "test-sandbox",
                "status": "provisioning",
                "status_message": None,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(
            snapshot_id="snap-1", wait_for_ready=False
        )

        assert sandbox.name == "test-sandbox"
        assert sandbox.status == "provisioning"
        assert sandbox.status_message is None

        request = httpx_mock.get_requests()[0]
        body = request.read()
        import json

        payload = json.loads(body)
        assert payload["wait_for_ready"] is False
        assert "timeout" not in payload

    async def test_get_sandbox_status(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test getting sandbox status."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "provisioning", "status_message": None},
        )

        status = await client.get_sandbox_status("my-sandbox")

        assert isinstance(status, ResourceStatus)
        assert status.status == "provisioning"

    async def test_get_sandbox_status_not_found(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test getting status of non-existent sandbox."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/nonexistent/status",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            await client.get_sandbox_status("nonexistent")

    async def test_wait_for_sandbox_ready(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test polling until sandbox is ready."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "provisioning", "status_message": None},
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "ready", "status_message": None},
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox",
                "status": "ready",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.wait_for_sandbox("my-sandbox", poll_interval=0.01)

        assert sandbox.name == "my-sandbox"
        assert sandbox.status == "ready"

    async def test_wait_for_sandbox_failed(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test polling detects failure."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={
                "status": "failed",
                "status_message": "No capacity available",
            },
        )

        with pytest.raises(
            ResourceCreationError, match="No capacity available"
        ) as exc_info:
            await client.wait_for_sandbox("my-sandbox", poll_interval=0.01)

        assert exc_info.value.resource_type == "sandbox"

    async def test_wait_for_sandbox_timeout(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test polling timeout."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "provisioning", "status_message": None},
        )

        with pytest.raises(ResourceTimeoutError) as exc_info:
            await client.wait_for_sandbox("my-sandbox", timeout=0, poll_interval=0.01)

        assert exc_info.value.last_status == "provisioning"

    async def test_create_sandbox_with_ttl(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox with TTL values."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "ttl_seconds": 3600,
                "idle_ttl_seconds": 600,
                "expires_at": "2026-03-24T12:00:00Z",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(
            snapshot_id="snap-1",
            ttl_seconds=3600,
            idle_ttl_seconds=600,
        )

        assert sandbox.ttl_seconds == 3600
        assert sandbox.idle_ttl_seconds == 600
        assert sandbox.expires_at == "2026-03-24T12:00:00Z"

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["ttl_seconds"] == 3600
        assert payload["idle_ttl_seconds"] == 600

    async def test_create_sandbox_ttl_omitted_when_none(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test TTL fields are omitted from payload when None."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        await client.create_sandbox(snapshot_id="snap-1")

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "ttl_seconds" not in payload
        assert "idle_ttl_seconds" not in payload

    async def test_create_sandbox_ttl_validation_negative(
        self, client: AsyncSandboxClient
    ):
        """Test that negative TTL values raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.create_sandbox(snapshot_id="snap-1", ttl_seconds=-1)

    async def test_create_sandbox_ttl_validation_not_multiple_of_60(
        self, client: AsyncSandboxClient
    ):
        """Test that non-multiple-of-60 TTL values raise ValueError."""
        with pytest.raises(ValueError, match="must be a multiple of 60"):
            await client.create_sandbox(snapshot_id="snap-1", ttl_seconds=90)

    async def test_create_sandbox_ttl_zero_allowed(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test that TTL value of 0 is allowed (disables TTL)."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "ttl_seconds": 0,
                "idle_ttl_seconds": 0,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(
            snapshot_id="snap-1",
            ttl_seconds=0,
            idle_ttl_seconds=0,
        )

        assert sandbox.ttl_seconds == 0
        assert sandbox.idle_ttl_seconds == 0

    async def test_update_sandbox_with_ttl(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a sandbox with TTL values."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox",
                "ttl_seconds": 7200,
                "idle_ttl_seconds": 1200,
                "expires_at": "2026-03-24T14:00:00Z",
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.update_sandbox(
            "my-sandbox",
            ttl_seconds=7200,
            idle_ttl_seconds=1200,
        )

        assert sandbox.ttl_seconds == 7200
        assert sandbox.idle_ttl_seconds == 1200
        assert sandbox.expires_at == "2026-03-24T14:00:00Z"

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["ttl_seconds"] == 7200
        assert payload["idle_ttl_seconds"] == 1200
        assert "name" not in payload

    async def test_update_sandbox_ttl_validation(self, client: AsyncSandboxClient):
        """Test that invalid TTL values raise ValueError on update."""
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.update_sandbox("my-sandbox", idle_ttl_seconds=-60)

    async def test_update_sandbox_name_and_ttl(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating sandbox name and TTL simultaneously."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox-renamed",
                "ttl_seconds": 3600,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.update_sandbox(
            "my-sandbox",
            new_name="my-sandbox-renamed",
            ttl_seconds=3600,
        )

        assert sandbox.name == "my-sandbox-renamed"
        assert sandbox.ttl_seconds == 3600

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["name"] == "my-sandbox-renamed"
        assert payload["ttl_seconds"] == 3600

    async def test_list_sandboxes_includes_status(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test that list_sandboxes parses status fields."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes",
            json={
                "sandboxes": [
                    {
                        "name": "sandbox-ready",
                        "status": "ready",
                    },
                    {
                        "name": "sandbox-provisioning",
                        "status": "provisioning",
                    },
                ]
            },
        )

        sandboxes = await client.list_sandboxes()

        assert len(sandboxes) == 2
        assert sandboxes[0].status == "ready"
        assert sandboxes[1].status == "provisioning"


class TestAsyncConnectionErrors:
    """Tests for async connection error handling."""

    async def test_connection_error_on_sandbox_create(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test connection error when creating sandbox."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            await client.create_sandbox(snapshot_id="snap-1")


class TestService:
    """Tests for AsyncSandboxClient.service()."""

    async def test_service_happy_path(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test getting a service URL returns AsyncServiceURL with correct fields."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-sandbox/service-url",
            json={
                "browser_url": "http://uuid--3000.svc.example.com/_svc/auth?token=jwt",
                "service_url": "http://uuid--3000.svc.example.com/",
                "token": "jwt-token",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )

        svc = await client.service("my-sandbox", 3000)

        assert isinstance(svc, AsyncServiceURL)
        assert svc.token == "jwt-token"
        assert svc.service_url == "http://uuid--3000.svc.example.com/"
        assert svc.expires_at == "2099-01-01T00:00:00Z"

    async def test_service_custom_expiry(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test custom expires_in_seconds is sent in payload."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-sandbox/service-url",
            json={
                "browser_url": "http://b",
                "service_url": "http://s/",
                "token": "t",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )

        await client.service("my-sandbox", 3000, expires_in_seconds=3600)

        request = httpx_mock.get_request()
        assert request is not None
        import json

        body = json.loads(request.content)
        assert body["port"] == 3000
        assert body["expires_in_seconds"] == 3600

    async def test_service_not_found(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test 404 raises ResourceNotFoundError."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/nonexistent/service-url",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            await client.service("nonexistent", 3000)

    async def test_service_invalid_port(self, client: AsyncSandboxClient):
        """Test port=0 raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            await client.service("my-sandbox", 0)

    async def test_service_invalid_expiry(self, client: AsyncSandboxClient):
        """Test expires_in_seconds=0 raises ValueError."""
        with pytest.raises(ValueError, match="between 1 and 86400"):
            await client.service("my-sandbox", 3000, expires_in_seconds=0)

    async def test_service_has_refresher(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test returned AsyncServiceURL has a working refresher."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-sandbox/service-url",
            json={
                "browser_url": "http://b1",
                "service_url": "http://s1/",
                "token": "token-1",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-sandbox/service-url",
            json={
                "browser_url": "http://b2",
                "service_url": "http://s2/",
                "token": "token-2",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )

        svc = await client.service("my-sandbox", 3000)
        assert svc._refresher is not None
        fresh = await svc._refresher()
        assert fresh._token == "token-2"
