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

    @pytest.mark.asyncio
    async def test_default_headers_attached_to_http_client(self):
        """Constructor headers flow to the HTTP client and are exposed for the
        WS exec path."""
        async with AsyncSandboxClient(
            api_endpoint="http://localhost:8080",
            api_key="api-key",
            headers={"X-Service-Key": "svc-jwt"},
        ) as client:
            assert client._http.headers.get("X-Service-Key") == "svc-jwt"
            assert client._http.headers.get("X-Api-Key") == "api-key"
            assert client._default_headers == {"X-Service-Key": "svc-jwt"}
            assert client._ws_default_headers(None) == {"X-Service-Key": "svc-jwt"}
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

    async def test_create_sandbox_with_retention(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Creating a sandbox with idle and delete-after-stop retention."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "idle_ttl_seconds": 600,
                "delete_after_stop_seconds": 86400,
                "stopped_at": None,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(
            snapshot_id="snap-1",
            idle_ttl_seconds=600,
            delete_after_stop_seconds=86400,
        )

        assert sandbox.idle_ttl_seconds == 600
        assert sandbox.delete_after_stop_seconds == 86400
        assert sandbox.stopped_at is None

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["idle_ttl_seconds"] == 600
        assert payload["delete_after_stop_seconds"] == 86400

    async def test_create_sandbox_retention_omitted_when_none(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Retention fields are omitted from payload when None."""
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
        assert "idle_ttl_seconds" not in payload
        assert "delete_after_stop_seconds" not in payload

    async def test_create_sandbox_retention_validation_negative(
        self, client: AsyncSandboxClient
    ):
        """Negative retention values raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.create_sandbox(snapshot_id="snap-1", idle_ttl_seconds=-1)
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.create_sandbox(
                snapshot_id="snap-1", delete_after_stop_seconds=-1
            )

    async def test_create_sandbox_retention_validation_not_multiple_of_60(
        self, client: AsyncSandboxClient
    ):
        """Non-multiple-of-60 retention values raise ValueError."""
        with pytest.raises(ValueError, match="must be a multiple of 60"):
            await client.create_sandbox(snapshot_id="snap-1", idle_ttl_seconds=90)
        with pytest.raises(ValueError, match="must be a multiple of 60"):
            await client.create_sandbox(
                snapshot_id="snap-1", delete_after_stop_seconds=90
            )

    async def test_create_sandbox_retention_zero_allowed(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Zero is accepted on both retention fields."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "idle_ttl_seconds": 0,
                "delete_after_stop_seconds": 0,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(
            snapshot_id="snap-1",
            idle_ttl_seconds=0,
            delete_after_stop_seconds=0,
        )

        assert sandbox.idle_ttl_seconds == 0
        assert sandbox.delete_after_stop_seconds == 0

    async def test_update_sandbox_with_retention(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Update both retention fields simultaneously."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox",
                "idle_ttl_seconds": 1200,
                "delete_after_stop_seconds": 7200,
                "stopped_at": None,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.update_sandbox(
            "my-sandbox",
            idle_ttl_seconds=1200,
            delete_after_stop_seconds=7200,
        )

        assert sandbox.idle_ttl_seconds == 1200
        assert sandbox.delete_after_stop_seconds == 7200
        assert sandbox.stopped_at is None

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["idle_ttl_seconds"] == 1200
        assert payload["delete_after_stop_seconds"] == 7200
        assert "name" not in payload

    async def test_update_sandbox_retention_validation(
        self, client: AsyncSandboxClient
    ):
        """Update path enforces the same retention bounds as create."""
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.update_sandbox("my-sandbox", idle_ttl_seconds=-60)
        with pytest.raises(ValueError, match="must be >= 0"):
            await client.update_sandbox("my-sandbox", delete_after_stop_seconds=-60)

    async def test_update_sandbox_name_and_retention(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Renaming and updating retention in one call."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox-renamed",
                "delete_after_stop_seconds": 3600,
                "dataplane_url": "https://sandbox-router.example.com/tenant/sb-123",
            },
        )

        sandbox = await client.update_sandbox(
            "my-sandbox",
            new_name="my-sandbox-renamed",
            delete_after_stop_seconds=3600,
        )

        assert sandbox.name == "my-sandbox-renamed"
        assert sandbox.delete_after_stop_seconds == 3600

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert payload["name"] == "my-sandbox-renamed"
        assert payload["delete_after_stop_seconds"] == 3600

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

    async def test_create_sandbox_with_snapshot_name(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox by snapshot name (server-side resolution)."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "my-vm",
                "snapshot_id": "snap-1",
                "status": "ready",
                "dataplane_url": "https://dp.example.com/my-vm",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(snapshot_name="my-snap", name="my-vm")

        assert sandbox.name == "my-vm"
        assert sandbox.snapshot_id == "snap-1"

        body = json.loads(httpx_mock.get_request().content)
        assert body["snapshot_name"] == "my-snap"
        assert "snapshot_id" not in body
        assert "template_name" not in body

    async def test_create_sandbox_omits_snapshot_id_when_absent(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox without a snapshot."""
        import json

        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "my-vm",
                "status": "ready",
                "dataplane_url": "https://dp.example.com/my-vm",
            },
            status_code=201,
        )

        sandbox = await client.create_sandbox(name="my-vm")

        assert sandbox.name == "my-vm"

        body = json.loads(httpx_mock.get_request().content)
        assert "snapshot_id" not in body
        assert "snapshot_name" not in body

    async def test_create_sandbox_rejects_both_snapshot_identifiers(
        self, client: AsyncSandboxClient
    ):
        """Test that snapshot_id / snapshot_name are mutually exclusive."""

        with pytest.raises(
            ValueError,
            match="At most one of snapshot_id or snapshot_name may be set",
        ):
            await client.create_sandbox(snapshot_id="snap-1", snapshot_name="my-snap")

    async def test_list_snapshots(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test listing snapshots with no filters."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots",
            json={
                "snapshots": [
                    {
                        "id": "snap-1",
                        "name": "env-1",
                        "status": "ready",
                    },
                ],
                "offset": 0,
            },
        )

        snapshots = await client.list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0].name == "env-1"

        request = httpx_mock.get_request()
        assert request.url.query == b""

    async def test_list_snapshots_with_filters(
        self, client: AsyncSandboxClient, httpx_mock: HTTPXMock
    ):
        """Test listing snapshots forwards name_contains/limit/offset."""
        httpx_mock.add_response(
            method="GET",
            url=(
                "http://test-server:8080/snapshots?name_contains=env&limit=10&offset=5"
            ),
            json={
                "snapshots": [
                    {
                        "id": "snap-1",
                        "name": "env-1",
                        "status": "ready",
                    }
                ],
                "offset": 5,
            },
        )

        snapshots = await client.list_snapshots(name_contains="env", limit=10, offset=5)

        assert len(snapshots) == 1
        assert snapshots[0].name == "env-1"

        request = httpx_mock.get_request()
        params = dict(request.url.params)
        assert params == {"name_contains": "env", "limit": "10", "offset": "5"}


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


class TestAsyncSandboxClientRepr:
    """Tests for __repr__ method to ensure sensitive info is not exposed."""

    async def test_repr_hides_api_key(self):
        """Test that __repr__ does not expose API key."""
        client = AsyncSandboxClient(
            api_endpoint="https://api.smith.langchain.com/v2/sandboxes",
            api_key="super-secret-api-key-12345",
        )
        repr_str = repr(client)
        # Ensure API key is NOT in the repr
        assert "super-secret-api-key-12345" not in repr_str
        # Ensure the repr shows the API URL
        assert "https://api.smith.langchain.com/v2/sandboxes" in repr_str
        # Ensure it's properly formatted
        assert (
            repr_str
            == "AsyncSandboxClient (API URL: https://api.smith.langchain.com/v2/sandboxes)"
        )
        await client.aclose()
