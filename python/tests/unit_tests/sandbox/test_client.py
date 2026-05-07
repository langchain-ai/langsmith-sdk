"""Tests for SandboxClient."""

from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    ResourceCreationError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceStatus,
    ResourceTimeoutError,
    SandboxClient,
    SandboxConnectionError,
    ServiceURL,
)


@pytest.fixture
def client():
    """Create a SandboxClient with retries disabled for test isolation."""
    return SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)


class TestSandboxClientInit:
    """Tests for client initialization."""

    def test_creates_with_explicit_endpoint(self):
        """Test client creation with explicit endpoint."""
        client = SandboxClient(api_endpoint="http://localhost:8080")
        assert client._base_url == "http://localhost:8080"
        client.close()

    def test_strips_trailing_slash(self):
        """Test trailing slash is stripped."""
        client = SandboxClient(api_endpoint="http://localhost:8080/")
        assert client._base_url == "http://localhost:8080"
        client.close()

    def test_context_manager(self):
        """Test context manager usage."""
        with SandboxClient(api_endpoint="http://localhost:8080") as client:
            assert client._base_url == "http://localhost:8080"

    def test_derives_endpoint_from_langsmith_endpoint(self):
        """Test endpoint derivation from LANGSMITH_ENDPOINT."""
        with patch(
            "langsmith.sandbox._client._get_default_api_endpoint",
            return_value="https://custom.langsmith.com/v2/sandboxes",
        ):
            client = SandboxClient()
            assert client._base_url == "https://custom.langsmith.com/v2/sandboxes"
            client.close()

    def test_derives_endpoint_from_langchain_endpoint(self):
        """Test endpoint derivation from LANGCHAIN_ENDPOINT (fallback)."""
        with patch(
            "langsmith.sandbox._client._get_default_api_endpoint",
            return_value="https://custom.langchain.com/v2/sandboxes",
        ):
            client = SandboxClient()
            assert client._base_url == "https://custom.langchain.com/v2/sandboxes"
            client.close()

    def test_explicit_endpoint_overrides_env(self):
        """Test explicit endpoint overrides environment variable."""
        with patch(
            "langsmith.sandbox._client._get_default_api_endpoint",
            return_value="https://env.langsmith.com/v2/sandboxes",
        ):
            client = SandboxClient(api_endpoint="http://explicit:8080")
            assert client._base_url == "http://explicit:8080"
            client.close()

    def test_api_key_from_parameter(self):
        """Test API key from parameter."""
        client = SandboxClient(
            api_endpoint="http://localhost:8080",
            api_key="test-key",
        )
        assert client._http.headers.get("X-Api-Key") == "test-key"
        client.close()

    def test_api_key_from_environment(self):
        """Test API key from environment variable."""
        with patch(
            "langsmith.sandbox._client._get_default_api_key",
            return_value="env-key",
        ):
            client = SandboxClient(api_endpoint="http://localhost:8080")
            assert client._http.headers.get("X-Api-Key") == "env-key"
            client.close()

    def test_explicit_api_key_overrides_env(self):
        """Test explicit API key overrides environment variable."""
        with patch(
            "langsmith.sandbox._client._get_default_api_key",
            return_value="env-key",
        ):
            client = SandboxClient(
                api_endpoint="http://localhost:8080",
                api_key="explicit-key",
            )
            assert client._http.headers.get("X-Api-Key") == "explicit-key"
            client.close()

    def test_max_retries_default(self):
        """Test default max_retries is 3."""
        from langsmith.sandbox._transport import RetryTransport

        client = SandboxClient(api_endpoint="http://localhost:8080")
        transport = client._http._transport
        assert isinstance(transport, RetryTransport)
        assert transport._max_retries == 3
        client.close()

    def test_max_retries_custom(self):
        """Test custom max_retries value."""
        from langsmith.sandbox._transport import RetryTransport

        client = SandboxClient(api_endpoint="http://localhost:8080", max_retries=5)
        transport = client._http._transport
        assert isinstance(transport, RetryTransport)
        assert transport._max_retries == 5
        client.close()

    def test_max_retries_zero_disables(self):
        """Test max_retries=0 disables retries."""
        from langsmith.sandbox._transport import RetryTransport

        client = SandboxClient(api_endpoint="http://localhost:8080", max_retries=0)
        transport = client._http._transport
        assert isinstance(transport, RetryTransport)
        assert transport._max_retries == 0
        client.close()


class TestSandboxOperations:
    """Tests for sandbox operations."""

    def test_create_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test creating a sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(snapshot_id="snap-1")

        assert sandbox.name == "test-sandbox"
        assert sandbox.id == "550e8400-e29b-41d4-a716-446655440003"
        assert sandbox.dataplane_url == "https://sandbox-router.example.com/sb-123"

    def test_create_sandbox_forwards_proxy_config(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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
        client.create_sandbox(
            snapshot_id="snap-1",
            proxy_config=proxy_config,
        )

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["proxy_config"] == proxy_config

    def test_create_sandbox_omits_proxy_config_when_none(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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

        client.create_sandbox(snapshot_id="snap-1")
        body = json.loads(httpx_mock.get_request().content)
        assert "proxy_config" not in body

    def test_create_sandbox_merges_custom_headers(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test per-request headers override default client headers."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        client.create_sandbox(
            snapshot_id="snap-1",
            headers={
                "X-Api-Key": "override-key",
                "X-Test-Header": "sandbox-client",
            },
        )

        request = httpx_mock.get_request()
        assert request.headers.get("X-Api-Key") == "override-key"
        assert request.headers.get("X-Test-Header") == "sandbox-client"

    def test_sandbox_context_manager(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox with context manager."""
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

        with client.sandbox(snapshot_id="snap-1") as sandbox:
            assert sandbox.name == "test-sandbox"

        # Verify delete was called
        requests = httpx_mock.get_requests()
        assert any(r.method == "DELETE" for r in requests)

    def test_sandbox_timeout(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test sandbox creation timeout."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={"detail": "Timeout waiting for sandbox to be ready"},
            status_code=408,
        )

        with pytest.raises(ResourceTimeoutError):
            client.create_sandbox(snapshot_id="snap-1")

    def test_list_sandboxes(self, client: SandboxClient, httpx_mock: HTTPXMock):
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

        sandboxes = client.list_sandboxes()

        assert len(sandboxes) == 1
        assert sandboxes[0].name == "sandbox-1"

    def test_delete_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a sandbox."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        # Should not raise
        client.delete_sandbox("test-sandbox")

    def test_update_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating a sandbox's name."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "my-sandbox-renamed",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
        )

        sandbox = client.update_sandbox("my-sandbox", new_name="my-sandbox-renamed")

        assert sandbox.name == "my-sandbox-renamed"
        assert sandbox.id == "550e8400-e29b-41d4-a716-446655440003"

    def test_update_sandbox_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a non-existent sandbox."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/nonexistent",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.update_sandbox("nonexistent", new_name="new-name")

    def test_update_sandbox_name_conflict(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating sandbox to a name that already exists."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={"detail": {"error": "Conflict", "message": "Name already in use"}},
            status_code=409,
        )

        with pytest.raises(ResourceNameConflictError) as exc_info:
            client.update_sandbox("my-sandbox", new_name="existing-sandbox")

        assert exc_info.value.resource_type == "sandbox"

    def test_create_sandbox_async_returns_provisioning(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(snapshot_id="snap-1", wait_for_ready=False)

        assert sandbox.name == "test-sandbox"
        assert sandbox.status == "provisioning"
        assert sandbox.status_message is None

        request = httpx_mock.get_requests()[0]
        body = request.read()
        import json

        payload = json.loads(body)
        assert payload["wait_for_ready"] is False
        assert "timeout" not in payload

    def test_create_sandbox_status_fields_parsed(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test that status fields are parsed from create response."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "status": "ready",
                "status_message": None,
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(snapshot_id="snap-1")

        assert sandbox.status == "ready"
        assert sandbox.status_message is None

    def test_get_sandbox_status(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting sandbox status."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "provisioning", "status_message": None},
        )

        status = client.get_sandbox_status("my-sandbox")

        assert isinstance(status, ResourceStatus)
        assert status.status == "provisioning"
        assert status.status_message is None

    def test_get_sandbox_status_failed(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test getting failed sandbox status."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={
                "status": "failed",
                "status_message": "No capacity available",
            },
        )

        status = client.get_sandbox_status("my-sandbox")

        assert status.status == "failed"
        assert status.status_message == "No capacity available"

    def test_get_sandbox_status_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test getting status of non-existent sandbox."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/nonexistent/status",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_sandbox_status("nonexistent")

    def test_wait_for_sandbox_ready(self, client: SandboxClient, httpx_mock: HTTPXMock):
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
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
        )

        sandbox = client.wait_for_sandbox("my-sandbox", poll_interval=0.01)

        assert sandbox.name == "my-sandbox"
        assert sandbox.status == "ready"

    def test_wait_for_sandbox_failed(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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
            client.wait_for_sandbox("my-sandbox", poll_interval=0.01)

        assert exc_info.value.resource_type == "sandbox"

    def test_wait_for_sandbox_timeout(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test polling timeout."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-sandbox/status",
            json={"status": "provisioning", "status_message": None},
        )

        with pytest.raises(ResourceTimeoutError) as exc_info:
            client.wait_for_sandbox("my-sandbox", timeout=0, poll_interval=0.01)

        assert exc_info.value.last_status == "provisioning"

    def test_create_sandbox_with_retention(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox with idle and delete-after-stop retention."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "idle_ttl_seconds": 600,
                "delete_after_stop_seconds": 86400,
                "stopped_at": None,
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(
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

    def test_create_sandbox_retention_omitted_when_none(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Retention fields are omitted from the payload when not specified."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        client.create_sandbox(snapshot_id="snap-1")

        import json

        request = httpx_mock.get_request()
        payload = json.loads(request.content)
        assert "idle_ttl_seconds" not in payload
        assert "delete_after_stop_seconds" not in payload

    def test_create_sandbox_retention_validation_negative(self, client: SandboxClient):
        """Negative retention values raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 0"):
            client.create_sandbox(snapshot_id="snap-1", idle_ttl_seconds=-1)
        with pytest.raises(ValueError, match="must be >= 0"):
            client.create_sandbox(snapshot_id="snap-1", delete_after_stop_seconds=-1)

    def test_create_sandbox_retention_validation_not_multiple_of_60(
        self, client: SandboxClient
    ):
        """Non-multiple-of-60 retention values raise ValueError."""
        with pytest.raises(ValueError, match="must be a multiple of 60"):
            client.create_sandbox(snapshot_id="snap-1", idle_ttl_seconds=90)
        with pytest.raises(ValueError, match="must be a multiple of 60"):
            client.create_sandbox(snapshot_id="snap-1", delete_after_stop_seconds=90)

    def test_create_sandbox_retention_zero_allowed(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Zero is accepted on both retention fields and disables that stage."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "idle_ttl_seconds": 0,
                "delete_after_stop_seconds": 0,
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(
            snapshot_id="snap-1",
            idle_ttl_seconds=0,
            delete_after_stop_seconds=0,
        )

        assert sandbox.idle_ttl_seconds == 0
        assert sandbox.delete_after_stop_seconds == 0

    def test_update_sandbox_with_retention(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
        )

        sandbox = client.update_sandbox(
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

    def test_update_sandbox_retention_validation(self, client: SandboxClient):
        """Update path enforces the same retention bounds as create."""
        with pytest.raises(ValueError, match="must be >= 0"):
            client.update_sandbox("my-sandbox", idle_ttl_seconds=-60)
        with pytest.raises(ValueError, match="must be >= 0"):
            client.update_sandbox("my-sandbox", delete_after_stop_seconds=-60)

    def test_update_sandbox_name_and_retention(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Renaming and updating retention in one call."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/my-sandbox",
            json={
                "name": "my-sandbox-renamed",
                "delete_after_stop_seconds": 3600,
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
        )

        sandbox = client.update_sandbox(
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

    def test_list_sandboxes_includes_status(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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

        sandboxes = client.list_sandboxes()

        assert len(sandboxes) == 2
        assert sandboxes[0].status == "ready"
        assert sandboxes[1].status == "provisioning"


class TestConnectionErrors:
    """Tests for connection error handling."""

    def test_connection_error_on_sandbox_create(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test connection error when creating sandbox."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            client.create_sandbox(snapshot_id="snap-1")


class TestService:
    """Tests for SandboxClient.service()."""

    def test_service_happy_path(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting a service URL returns ServiceURL with correct fields."""
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

        svc = client.service("my-sandbox", 3000)

        assert isinstance(svc, ServiceURL)
        assert svc.token == "jwt-token"
        assert svc.service_url == "http://uuid--3000.svc.example.com/"
        assert svc.browser_url.endswith("?token=jwt")
        assert svc.expires_at == "2099-01-01T00:00:00Z"

    def test_service_custom_expiry(self, client: SandboxClient, httpx_mock: HTTPXMock):
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

        client.service("my-sandbox", 3000, expires_in_seconds=3600)

        request = httpx_mock.get_request()
        assert request is not None
        import json

        body = json.loads(request.content)
        assert body["port"] == 3000
        assert body["expires_in_seconds"] == 3600

    def test_service_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test 404 raises ResourceNotFoundError."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/nonexistent/service-url",
            json={"detail": "Sandbox 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.service("nonexistent", 3000)

    def test_service_invalid_port_zero(self, client: SandboxClient):
        """Test port=0 raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            client.service("my-sandbox", 0)

    def test_service_invalid_port_negative(self, client: SandboxClient):
        """Test negative port raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            client.service("my-sandbox", -1)

    def test_service_invalid_port_string(self, client: SandboxClient):
        """Test non-integer port raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            client.service("my-sandbox", "3000")  # type: ignore[arg-type]

    def test_service_invalid_expiry_zero(self, client: SandboxClient):
        """Test expires_in_seconds=0 raises ValueError."""
        with pytest.raises(ValueError, match="between 1 and 86400"):
            client.service("my-sandbox", 3000, expires_in_seconds=0)

    def test_service_invalid_expiry_too_large(self, client: SandboxClient):
        """Test expires_in_seconds > 86400 raises ValueError."""
        with pytest.raises(ValueError, match="between 1 and 86400"):
            client.service("my-sandbox", 3000, expires_in_seconds=86401)

    def test_service_has_refresher(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test returned ServiceURL has a working refresher."""
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

        svc = client.service("my-sandbox", 3000)
        assert svc._refresher is not None
        fresh = svc._refresher()
        assert fresh._token == "token-2"


class TestSnapshotOperations:
    """Tests for snapshot operations."""

    def test_create_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test building a snapshot from a Docker image."""
        # First response: POST /snapshots returns building snapshot
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/snapshots",
            json={
                "id": "snap-1",
                "name": "my-env",
                "status": "building",
                "fs_capacity_bytes": 4294967296,
                "docker_image": "python:3.12-slim",
            },
            status_code=201,
        )
        # Second response: GET /snapshots/snap-1 returns ready
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "my-env",
                "status": "ready",
                "fs_capacity_bytes": 4294967296,
                "docker_image": "python:3.12-slim",
            },
        )

        snapshot = client.create_snapshot("my-env", "python:3.12-slim", 4294967296)

        assert snapshot.id == "snap-1"
        assert snapshot.status == "ready"

    def test_capture_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test capturing a snapshot from a running sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-vm/snapshot",
            json={
                "id": "snap-2",
                "name": "captured",
                "status": "building",
                "fs_capacity_bytes": 4294967296,
                "source_sandbox_id": "my-vm",
            },
            status_code=201,
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-2",
            json={
                "id": "snap-2",
                "name": "captured",
                "status": "ready",
                "fs_capacity_bytes": 4294967296,
                "source_sandbox_id": "my-vm",
            },
        )

        snapshot = client.capture_snapshot("my-vm", "captured")

        assert snapshot.id == "snap-2"
        assert snapshot.status == "ready"
        assert snapshot.source_sandbox_id == "my-vm"

    def test_capture_snapshot_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test capturing from a non-existent sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/nonexistent/snapshot",
            json={"detail": {"error": "not_found", "message": "not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.capture_snapshot("nonexistent", "snap")

    def test_get_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting a snapshot by ID."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "my-env",
                "status": "ready",
                "fs_capacity_bytes": 4294967296,
            },
        )

        snapshot = client.get_snapshot("snap-1")

        assert snapshot.id == "snap-1"
        assert snapshot.name == "my-env"

    def test_get_snapshot_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting a non-existent snapshot."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/nonexistent",
            json={"detail": {"error": "not_found", "message": "not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_snapshot("nonexistent")

    def test_list_snapshots(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test listing snapshots."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots",
            json={
                "snapshots": [
                    {
                        "id": "snap-1",
                        "name": "env-1",
                        "status": "ready",
                        "fs_capacity_bytes": 4294967296,
                    },
                    {
                        "id": "snap-2",
                        "name": "env-2",
                        "status": "building",
                        "fs_capacity_bytes": 8589934592,
                    },
                ],
                "offset": 0,
            },
        )

        snapshots = client.list_snapshots()

        assert len(snapshots) == 2
        assert snapshots[0].name == "env-1"
        assert snapshots[1].status == "building"

        request = httpx_mock.get_request()
        assert request.url.query == b""

    def test_list_snapshots_with_filters(
        self, client: SandboxClient, httpx_mock: HTTPXMock
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

        snapshots = client.list_snapshots(name_contains="env", limit=10, offset=5)

        assert len(snapshots) == 1
        assert snapshots[0].name == "env-1"

        request = httpx_mock.get_request()
        params = dict(request.url.params)
        assert params == {"name_contains": "env", "limit": "10", "offset": "5"}

    def test_delete_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a snapshot."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/snapshots/snap-1",
            status_code=204,
        )

        client.delete_snapshot("snap-1")

    def test_delete_snapshot_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test deleting a non-existent snapshot."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/snapshots/nonexistent",
            json={"detail": {"error": "not_found", "message": "not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.delete_snapshot("nonexistent")

    def test_wait_for_snapshot_immediate_ready(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test waiting for an already-ready snapshot."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "env",
                "status": "ready",
                "fs_capacity_bytes": 4294967296,
            },
        )

        snapshot = client.wait_for_snapshot("snap-1")
        assert snapshot.status == "ready"

    def test_wait_for_snapshot_failed(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test waiting for a snapshot that fails."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "env",
                "status": "failed",
                "status_message": "Docker pull failed",
                "fs_capacity_bytes": 4294967296,
            },
        )

        with pytest.raises(ResourceCreationError, match="Docker pull failed"):
            client.wait_for_snapshot("snap-1")


class TestStartStopOperations:
    """Tests for sandbox start/stop lifecycle."""

    def test_start_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test starting a stopped sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-vm/start",
            json={},
            status_code=202,
        )
        # wait_for_sandbox polls status then gets full sandbox
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-vm/status",
            json={"status": "ready"},
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes/my-vm",
            json={
                "name": "my-vm",
                "status": "ready",
                "dataplane_url": "https://dp.example.com/my-vm",
            },
        )

        sandbox = client.start_sandbox("my-vm")

        assert sandbox.name == "my-vm"
        assert sandbox.status == "ready"
        assert sandbox.dataplane_url == "https://dp.example.com/my-vm"

    def test_start_sandbox_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test starting a non-existent sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/nonexistent/start",
            json={"detail": {"error": "not_found", "message": "not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.start_sandbox("nonexistent")

    def test_stop_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test stopping a sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/my-vm/stop",
            status_code=204,
        )

        client.stop_sandbox("my-vm")

    def test_stop_sandbox_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test stopping a non-existent sandbox."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/nonexistent/stop",
            json={"detail": {"error": "not_found", "message": "not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.stop_sandbox("nonexistent")

    def test_create_sandbox_with_snapshot_id(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox from a snapshot."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "my-vm",
                "snapshot_id": "snap-1",
                "status": "ready",
                "dataplane_url": "https://dp.example.com/my-vm",
                "vcpus": 4,
                "mem_bytes": 1073741824,
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(snapshot_id="snap-1", name="my-vm")

        assert sandbox.name == "my-vm"
        assert sandbox.snapshot_id == "snap-1"
        assert sandbox.vcpus == 4
        assert sandbox.mem_bytes == 1073741824

        import json

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["snapshot_id"] == "snap-1"
        assert "snapshot_name" not in body
        assert "template_name" not in body

    def test_create_sandbox_with_snapshot_name(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a sandbox by snapshot name (server-side resolution)."""
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

        sandbox = client.create_sandbox(snapshot_name="my-snap", name="my-vm")

        assert sandbox.name == "my-vm"
        assert sandbox.snapshot_id == "snap-1"

        import json

        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert body["snapshot_name"] == "my-snap"
        assert "snapshot_id" not in body
        assert "template_name" not in body

    def test_create_sandbox_requires_exactly_one_identifier(
        self, client: SandboxClient
    ):
        """Test that exactly one of snapshot_id / snapshot_name must be set."""
        with pytest.raises(
            ValueError,
            match="Exactly one of snapshot_id or snapshot_name must be set",
        ):
            client.create_sandbox()

        with pytest.raises(
            ValueError,
            match="Exactly one of snapshot_id or snapshot_name must be set",
        ):
            client.create_sandbox(snapshot_id="snap-1", snapshot_name="my-snap")


class TestSandboxClientRepr:
    """Tests for __repr__ method to ensure sensitive info is not exposed."""

    def test_repr_hides_api_key(self):
        """Test that __repr__ does not expose API key."""
        client = SandboxClient(
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
            == "SandboxClient (API URL: https://api.smith.langchain.com/v2/sandboxes)"
        )
        client.close()
