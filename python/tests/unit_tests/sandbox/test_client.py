"""Tests for SandboxClient."""

from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    QuotaExceededError,
    ResourceAlreadyExistsError,
    ResourceInUseError,
    ResourceNameConflictError,
    ResourceNotFoundError,
    ResourceTimeoutError,
    SandboxClient,
    SandboxConnectionError,
    ValidationError,
)


@pytest.fixture
def client():
    """Create a SandboxClient."""
    return SandboxClient(api_endpoint="http://test-server:8080")


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
            return_value="https://custom.langsmith.com/api/v2/sandboxes",
        ):
            client = SandboxClient()
            assert client._base_url == "https://custom.langsmith.com/api/v2/sandboxes"
            client.close()

    def test_derives_endpoint_from_langchain_endpoint(self):
        """Test endpoint derivation from LANGCHAIN_ENDPOINT (fallback)."""
        with patch(
            "langsmith.sandbox._client._get_default_api_endpoint",
            return_value="https://custom.langchain.com/api/v2/sandboxes",
        ):
            client = SandboxClient()
            assert client._base_url == "https://custom.langchain.com/api/v2/sandboxes"
            client.close()

    def test_explicit_endpoint_overrides_env(self):
        """Test explicit endpoint overrides environment variable."""
        with patch(
            "langsmith.sandbox._client._get_default_api_endpoint",
            return_value="https://env.langsmith.com/api/v2/sandboxes",
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


class TestTemplateOperations:
    """Tests for template operations."""

    def test_create_template(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test creating a template."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/templates",
            json={
                "name": "python-sandbox",
                "image": "python:3.12-slim",
                "resources": {"cpu": "500m", "memory": "512Mi"},
            },
            status_code=201,
        )

        template = client.create_template(
            name="python-sandbox",
            image="python:3.12-slim",
        )

        assert template.name == "python-sandbox"
        assert template.image == "python:3.12-slim"

    def test_create_template_with_resources(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating a template with custom resources."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/templates",
            json={
                "name": "python-sandbox",
                "image": "python:3.12-slim",
                "resources": {"cpu": "2", "memory": "4Gi", "storage": "10Gi"},
            },
            status_code=201,
        )

        template = client.create_template(
            name="python-sandbox",
            image="python:3.12-slim",
            cpu="2",
            memory="4Gi",
            storage="10Gi",
        )

        assert template.resources.cpu == "2"
        assert template.resources.memory == "4Gi"
        assert template.resources.storage == "10Gi"

    def test_list_templates(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test listing templates."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/templates",
            json={
                "templates": [
                    {
                        "name": "template-1",
                        "image": "python:3.12",
                        "resources": {"cpu": "500m", "memory": "512Mi"},
                    },
                    {
                        "name": "template-2",
                        "image": "node:20",
                        "resources": {"cpu": "1", "memory": "1Gi"},
                    },
                ]
            },
        )

        templates = client.list_templates()

        assert len(templates) == 2
        assert templates[0].name == "template-1"
        assert templates[1].name == "template-2"

    def test_get_template(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting a template."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/templates/python-sandbox",
            json={
                "name": "python-sandbox",
                "image": "python:3.12-slim",
                "resources": {"cpu": "500m", "memory": "512Mi"},
            },
        )

        template = client.get_template("python-sandbox")

        assert template.name == "python-sandbox"

    def test_get_template_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting non-existent template."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/templates/nonexistent",
            json={"detail": "Template 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_template("nonexistent")

    def test_update_template(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating a template's name."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/templates/python-sandbox",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "python-sandbox-renamed",
                "image": "python:3.12-slim",
                "resources": {"cpu": "500m", "memory": "512Mi"},
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        template = client.update_template(
            "python-sandbox", new_name="python-sandbox-renamed"
        )

        assert template.name == "python-sandbox-renamed"
        assert template.id == "550e8400-e29b-41d4-a716-446655440001"
        assert template.updated_at == "2026-01-19T14:00:00Z"

    def test_update_template_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a non-existent template."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/templates/nonexistent",
            json={"detail": "Template 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.update_template("nonexistent", new_name="new-name")

    def test_update_template_name_conflict(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a template to a name that already exists."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/templates/python-sandbox",
            json={
                "detail": {
                    "error": "Conflict",
                    "message": "Template name 'existing-template' is already in use",
                }
            },
            status_code=409,
        )

        with pytest.raises(ResourceNameConflictError) as exc_info:
            client.update_template("python-sandbox", new_name="existing-template")
        assert exc_info.value.resource_type == "template"

    def test_delete_template(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a template."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/templates/python-sandbox",
            status_code=204,
        )

        # Should not raise
        client.delete_template("python-sandbox")

    def test_delete_template_in_use(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a template that is in use by sandboxes or pools."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/templates/python-sandbox",
            json={
                "detail": {
                    "error": "Conflict",
                    "message": (
                        "Template 'python-sandbox' is in use by sandboxes: sandbox-1; "
                        "pools: pool-1. Delete the dependent resources first."
                    ),
                }
            },
            status_code=409,
        )

        with pytest.raises(ResourceInUseError):
            client.delete_template("python-sandbox")


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
                "template_name": "python-sandbox",
                "dataplane_url": "https://sandbox-router.example.com/sb-123",
            },
            status_code=201,
        )

        sandbox = client.create_sandbox(template_name="python-sandbox")

        assert sandbox.name == "test-sandbox"
        assert sandbox.id == "550e8400-e29b-41d4-a716-446655440003"
        assert sandbox.dataplane_url == "https://sandbox-router.example.com/sb-123"

    def test_sandbox_context_manager(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test sandbox with context manager."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={
                "name": "test-sandbox",
                "template_name": "python-sandbox",
            },
            status_code=201,
        )
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/boxes/test-sandbox",
            status_code=204,
        )

        with client.sandbox(template_name="python-sandbox") as sandbox:
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
            client.create_sandbox(template_name="python-sandbox")

    def test_list_sandboxes(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test listing sandboxes."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/boxes",
            json={
                "sandboxes": [
                    {
                        "name": "sandbox-1",
                        "template_name": "template-1",
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
                "template_name": "python-sandbox",
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


class TestPoolOperations:
    """Tests for pool operations."""

    def test_create_pool(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test creating a pool."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "name": "python-pool",
                "template_name": "python-sandbox",
                "replicas": 5,
                "created_at": "2026-01-16T12:00:00Z",
            },
            status_code=201,
        )

        pool = client.create_pool(
            name="python-pool",
            template_name="python-sandbox",
            replicas=5,
        )

        assert pool.name == "python-pool"
        assert pool.template_name == "python-sandbox"
        assert pool.replicas == 5

    def test_create_pool_template_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating pool with non-existent template."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "detail": {
                    "error": "TemplateNotFound",
                    "message": "Template 'nonexistent' not found.",
                }
            },
            status_code=400,
        )

        with pytest.raises(ResourceNotFoundError):
            client.create_pool(
                name="python-pool",
                template_name="nonexistent",
                replicas=5,
            )

    def test_create_pool_template_has_volumes(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating pool with template that has volumes."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "detail": {
                    "error": "ValidationError",
                    "message": (
                        "Template 'stateful-template' has volumes attached. "
                        "Pools only support stateless templates."
                    ),
                }
            },
            status_code=400,
        )

        with pytest.raises(ValidationError) as exc_info:
            client.create_pool(
                name="python-pool",
                template_name="stateful-template",
                replicas=5,
            )
        assert exc_info.value.error_type == "ValidationError"

    def test_create_pool_already_exists(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating pool that already exists."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={"detail": "Pool 'python-pool' already exists"},
            status_code=409,
        )

        with pytest.raises(ResourceAlreadyExistsError):
            client.create_pool(
                name="python-pool",
                template_name="python-sandbox",
                replicas=5,
            )

    def test_create_pool_quota_exceeded(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating pool when quota is exceeded."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "detail": (
                    "Limit of 10 sandbox(es) per organization exceeded. "
                    "Current usage: 8 sandboxes, Requested: 5 additional."
                )
            },
            status_code=429,
        )

        with pytest.raises(QuotaExceededError) as exc_info:
            client.create_pool(
                name="python-pool",
                template_name="python-sandbox",
                replicas=5,
            )
        assert exc_info.value.quota_type == "sandbox_count"

    def test_create_pool_with_timeout(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test creating pool sends wait_for_ready and timeout in payload."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "name": "python-pool",
                "template_name": "python-sandbox",
                "replicas": 5,
                "created_at": "2026-01-16T12:00:00Z",
            },
            status_code=201,
        )

        pool = client.create_pool(
            name="python-pool",
            template_name="python-sandbox",
            replicas=5,
            timeout=60,
        )

        assert pool.name == "python-pool"
        assert pool.replicas == 5

        # Verify the request payload includes wait_for_ready (hardcoded) and timeout
        request = httpx_mock.get_request()
        import json

        body = json.loads(request.content)
        assert body["wait_for_ready"] is True
        assert body["timeout"] == 60

    def test_create_pool_timeout(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test creating pool timeout when waiting for ready."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/pools",
            json={
                "detail": {
                    "error": "Timeout",
                    "message": (
                        "Pool 'python-pool' did not reach 1 ready replica(s) "
                        "within 30 seconds"
                    ),
                }
            },
            status_code=504,
        )

        with pytest.raises(ResourceTimeoutError):
            client.create_pool(
                name="python-pool",
                template_name="python-sandbox",
                replicas=5,
            )

    def test_get_pool(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting a pool."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/pools/python-pool",
            json={
                "name": "python-pool",
                "template_name": "python-sandbox",
                "replicas": 5,
                "created_at": "2026-01-16T12:00:00Z",
            },
        )

        pool = client.get_pool("python-pool")

        assert pool.name == "python-pool"
        assert pool.replicas == 5

    def test_get_pool_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test getting non-existent pool."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/pools/nonexistent",
            json={"detail": "Pool 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.get_pool("nonexistent")

    def test_list_pools(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test listing pools."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/pools",
            json={
                "pools": [
                    {
                        "name": "pool-1",
                        "template_name": "python-sandbox",
                        "replicas": 5,
                    },
                    {
                        "name": "pool-2",
                        "template_name": "node-sandbox",
                        "replicas": 3,
                    },
                ]
            },
        )

        pools = client.list_pools()

        assert len(pools) == 2
        assert pools[0].name == "pool-1"
        assert pools[1].name == "pool-2"

    def test_list_pools_empty(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test listing pools when none exist."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/pools",
            json={"pools": []},
        )

        pools = client.list_pools()

        assert len(pools) == 0

    def test_update_pool_replicas(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating pool replicas."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "python-pool",
                "template_name": "python-sandbox",
                "replicas": 10,
                "created_at": "2026-01-16T12:00:00Z",
            },
        )

        pool = client.update_pool("python-pool", replicas=10)

        assert pool.name == "python-pool"
        assert pool.replicas == 10

    def test_update_pool_name(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating pool name."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "python-pool-renamed",
                "template_name": "python-sandbox",
                "replicas": 5,
                "created_at": "2026-01-16T12:00:00Z",
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        pool = client.update_pool("python-pool", new_name="python-pool-renamed")

        assert pool.name == "python-pool-renamed"
        assert pool.id == "550e8400-e29b-41d4-a716-446655440002"

    def test_update_pool_name_and_replicas(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating pool name and replicas in a single request."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "python-pool-renamed",
                "template_name": "python-sandbox",
                "replicas": 10,
                "created_at": "2026-01-16T12:00:00Z",
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        pool = client.update_pool(
            "python-pool", new_name="python-pool-renamed", replicas=10
        )

        assert pool.name == "python-pool-renamed"
        assert pool.replicas == 10

    def test_update_pool_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating non-existent pool."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/nonexistent",
            json={"detail": "Pool 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.update_pool("nonexistent", replicas=10)

    def test_update_pool_quota_exceeded(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating pool when scaling up exceeds quota."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={"detail": "Limit of 10 sandbox(es) per organization exceeded."},
            status_code=429,
        )

        with pytest.raises(QuotaExceededError):
            client.update_pool("python-pool", replicas=20)

    def test_update_pool_pause(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test pausing pool by setting replicas to 0."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={
                "name": "python-pool",
                "template_name": "python-sandbox",
                "replicas": 0,
            },
        )

        pool = client.update_pool("python-pool", replicas=0)

        assert pool.replicas == 0

    def test_update_pool_name_conflict(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a pool to a name that already exists."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/pools/python-pool",
            json={
                "detail": {
                    "error": "Conflict",
                    "message": "Pool name 'existing-pool' is already in use",
                }
            },
            status_code=409,
        )

        with pytest.raises(ResourceNameConflictError) as exc_info:
            client.update_pool("python-pool", new_name="existing-pool")
        assert exc_info.value.resource_type == "pool"

    def test_delete_pool(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a pool."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/pools/python-pool",
            status_code=204,
        )

        # Should not raise
        client.delete_pool("python-pool")

    def test_delete_pool_not_found(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting non-existent pool."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/pools/nonexistent",
            json={"detail": "Pool 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.delete_pool("nonexistent")


class TestConnectionErrors:
    """Tests for connection error handling."""

    def test_connection_error_on_template_create(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test connection error when creating template."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            client.create_template(name="test", image="python:3.12")

    def test_connection_error_on_sandbox_create(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test connection error when creating sandbox."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            client.create_sandbox(template_name="test")

    def test_connection_error_on_pool_create(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test connection error when creating pool."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        with pytest.raises(SandboxConnectionError):
            client.create_pool(
                name="python-pool",
                template_name="python-sandbox",
                replicas=5,
            )


class TestVolumeOperations:
    """Tests for volume operations."""

    def test_update_volume_size(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating a volume's size."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "my-volume",
                "size": "20Gi",
                "storage_class": "standard",
                "created_at": "2026-01-19T12:00:00Z",
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        volume = client.update_volume("my-volume", size="20Gi")

        assert volume.name == "my-volume"
        assert volume.size == "20Gi"
        assert volume.updated_at == "2026-01-19T14:00:00Z"

    def test_update_volume_name(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test updating a volume's name."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "my-volume-renamed",
                "size": "10Gi",
                "storage_class": "standard",
                "created_at": "2026-01-19T12:00:00Z",
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        volume = client.update_volume("my-volume", new_name="my-volume-renamed")

        assert volume.name == "my-volume-renamed"
        assert volume.id == "550e8400-e29b-41d4-a716-446655440000"

    def test_update_volume_name_and_size(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating both volume name and size in a single request."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "my-volume-renamed",
                "size": "20Gi",
                "storage_class": "standard",
                "created_at": "2026-01-19T12:00:00Z",
                "updated_at": "2026-01-19T14:00:00Z",
            },
        )

        volume = client.update_volume(
            "my-volume", new_name="my-volume-renamed", size="20Gi"
        )

        assert volume.name == "my-volume-renamed"
        assert volume.size == "20Gi"

    def test_update_volume_not_found(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a non-existent volume."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/nonexistent",
            json={"detail": "Volume 'nonexistent' not found"},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError):
            client.update_volume("nonexistent", size="20Gi")

    def test_update_volume_resize_error(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a volume with size decrease."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "detail": {
                    "error": "ResizeError",
                    "message": (
                        "Volume 'my-volume' resize failed: Storage cannot be "
                        "decreased. Current: 10.00Gi, Requested: 5.00Gi"
                    ),
                }
            },
            status_code=400,
        )

        with pytest.raises(ValidationError):
            client.update_volume("my-volume", size="5Gi")

    def test_update_volume_name_conflict(
        self, client: SandboxClient, httpx_mock: HTTPXMock
    ):
        """Test updating a volume to a name that already exists."""
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "detail": {
                    "error": "Conflict",
                    "message": "Volume name 'existing-volume' is already in use",
                }
            },
            status_code=409,
        )

        with pytest.raises(ResourceNameConflictError) as exc_info:
            client.update_volume("my-volume", new_name="existing-volume")
        assert exc_info.value.resource_type == "volume"

    def test_delete_volume_in_use(self, client: SandboxClient, httpx_mock: HTTPXMock):
        """Test deleting a volume that is in use by templates."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-server:8080/volumes/my-volume",
            json={
                "detail": {
                    "error": "Conflict",
                    "message": (
                        "Volume 'my-volume' is in use by templates: template-1, "
                        "template-2. Delete or update the templates first."
                    ),
                }
            },
            status_code=409,
        )

        with pytest.raises(ResourceInUseError):
            client.delete_volume("my-volume")
