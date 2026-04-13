"""Tests for sandbox data models."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from langsmith.sandbox import (
    AsyncServiceURL,
    ExecutionResult,
    OutputChunk,
    Pool,
    ResourceSpec,
    ResourceStatus,
    SandboxTemplate,
    ServiceURL,
    Volume,
    VolumeMountSpec,
)


class TestOutputChunk:
    """Tests for OutputChunk."""

    def test_dataclass(self):
        """Test OutputChunk fields."""
        chunk = OutputChunk(stream="stdout", data="hello", offset=0)
        assert chunk.stream == "stdout"
        assert chunk.data == "hello"
        assert chunk.offset == 0


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_success_property_true(self):
        """Test success is True when exit_code is 0."""
        result = ExecutionResult(stdout="output", stderr="", exit_code=0)
        assert result.success is True

    def test_success_property_false(self):
        """Test success is False when exit_code is non-zero."""
        result = ExecutionResult(stdout="", stderr="error", exit_code=1)
        assert result.success is False

    def test_success_property_negative_exit(self):
        """Test success is False when exit_code is negative."""
        result = ExecutionResult(stdout="", stderr="", exit_code=-1)
        assert result.success is False


class TestResourceSpec:
    """Tests for ResourceSpec."""

    def test_default_values(self):
        """Test default values."""
        spec = ResourceSpec()
        assert spec.cpu == "500m"
        assert spec.memory == "512Mi"
        assert spec.storage is None

    def test_custom_values(self):
        """Test custom values."""
        spec = ResourceSpec(cpu="1", memory="1Gi", storage="5Gi")
        assert spec.cpu == "1"
        assert spec.memory == "1Gi"
        assert spec.storage == "5Gi"


class TestVolume:
    """Tests for Volume."""

    def test_from_dict(self):
        """Test creating from dict."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "test-volume",
            "size": "1Gi",
            "storage_class": "hostpath",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        }
        volume = Volume.from_dict(data)

        assert volume.id == "550e8400-e29b-41d4-a716-446655440000"
        assert volume.name == "test-volume"
        assert volume.size == "1Gi"
        assert volume.storage_class == "hostpath"
        assert volume.created_at == "2025-01-01T00:00:00Z"
        assert volume.updated_at == "2025-01-02T00:00:00Z"

    def test_from_dict_minimal(self):
        """Test creating from minimal dict."""
        data = {
            "name": "test-volume",
            "size": "5Gi",
        }
        volume = Volume.from_dict(data)

        assert volume.id is None
        assert volume.name == "test-volume"
        assert volume.size == "5Gi"
        assert volume.storage_class == "default"
        assert volume.created_at is None
        assert volume.updated_at is None


class TestVolumeMountSpec:
    """Tests for VolumeMountSpec."""

    def test_creation(self):
        """Test creating a volume mount spec."""
        mount = VolumeMountSpec(volume_name="my-volume", mount_path="/data")
        assert mount.volume_name == "my-volume"
        assert mount.mount_path == "/data"


class TestSandboxTemplate:
    """Tests for SandboxTemplate."""

    def test_from_dict_minimal(self):
        """Test creating from minimal dict."""
        data = {
            "name": "test-template",
            "image": "python:3.12",
        }
        template = SandboxTemplate.from_dict(data)

        assert template.id is None
        assert template.name == "test-template"
        assert template.image == "python:3.12"
        assert template.resources.cpu == "500m"
        assert template.updated_at is None

    def test_from_dict_full(self):
        """Test creating from full dict."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "test-template",
            "image": "node:20",
            "resources": {
                "cpu": "2",
                "memory": "4Gi",
                "storage": "10Gi",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        }
        template = SandboxTemplate.from_dict(data)

        assert template.id == "550e8400-e29b-41d4-a716-446655440001"
        assert template.name == "test-template"
        assert template.image == "node:20"
        assert template.resources.cpu == "2"
        assert template.resources.memory == "4Gi"
        assert template.resources.storage == "10Gi"
        assert template.created_at == "2025-01-01T00:00:00Z"
        assert template.updated_at == "2025-01-02T00:00:00Z"

    def test_from_dict_with_volume_mounts(self):
        """Test creating from dict with volume mounts."""
        data = {
            "name": "test-template",
            "image": "python:3.12",
            "volume_mounts": [
                {"volume_name": "data-volume", "mount_path": "/data"},
                {"volume_name": "cache-volume", "mount_path": "/cache"},
            ],
        }
        template = SandboxTemplate.from_dict(data)

        assert len(template.volume_mounts) == 2
        assert template.volume_mounts[0].volume_name == "data-volume"
        assert template.volume_mounts[0].mount_path == "/data"
        assert template.volume_mounts[1].volume_name == "cache-volume"
        assert template.volume_mounts[1].mount_path == "/cache"

    def test_from_dict_empty_volume_mounts(self):
        """Test creating from dict with empty volume mounts."""
        data = {
            "name": "test-template",
            "image": "python:3.12",
            "volume_mounts": [],
        }
        template = SandboxTemplate.from_dict(data)

        assert template.volume_mounts == []

    def test_from_dict_no_volume_mounts_key(self):
        """Test creating from dict without volume_mounts key."""
        data = {
            "name": "test-template",
            "image": "python:3.12",
        }
        template = SandboxTemplate.from_dict(data)

        assert template.volume_mounts == []


class TestResourceStatus:
    """Tests for ResourceStatus."""

    def test_from_dict_provisioning(self):
        """Test creating from provisioning response."""
        data = {"status": "provisioning", "status_message": None}
        status = ResourceStatus.from_dict(data)
        assert status.status == "provisioning"
        assert status.status_message is None

    def test_from_dict_ready(self):
        """Test creating from ready response."""
        data = {"status": "ready", "status_message": None}
        status = ResourceStatus.from_dict(data)
        assert status.status == "ready"
        assert status.status_message is None

    def test_from_dict_failed(self):
        """Test creating from failed response with message."""
        data = {
            "status": "failed",
            "status_message": "No capacity available",
        }
        status = ResourceStatus.from_dict(data)
        assert status.status == "failed"
        assert status.status_message == "No capacity available"

    def test_from_dict_defaults(self):
        """Test defaults when keys are missing."""
        status = ResourceStatus.from_dict({})
        assert status.status == "provisioning"
        assert status.status_message is None


class TestPool:
    """Tests for Pool."""

    def test_from_dict_full(self):
        """Test creating from full dict."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "name": "python-pool",
            "template_name": "python-sandbox",
            "replicas": 5,
            "created_at": "2026-01-16T12:00:00Z",
            "updated_at": "2026-01-16T14:30:00Z",
        }
        pool = Pool.from_dict(data)

        assert pool.id == "550e8400-e29b-41d4-a716-446655440002"
        assert pool.name == "python-pool"
        assert pool.template_name == "python-sandbox"
        assert pool.replicas == 5
        assert pool.created_at == "2026-01-16T12:00:00Z"
        assert pool.updated_at == "2026-01-16T14:30:00Z"

    def test_from_dict_minimal(self):
        """Test creating from minimal dict."""
        data = {
            "name": "python-pool",
            "template_name": "python-sandbox",
            "replicas": 3,
        }
        pool = Pool.from_dict(data)

        assert pool.id is None
        assert pool.name == "python-pool"
        assert pool.template_name == "python-sandbox"
        assert pool.replicas == 3
        assert pool.created_at is None
        assert pool.updated_at is None

    def test_from_dict_paused(self):
        """Test creating from dict for paused pool."""
        data = {
            "name": "paused-pool",
            "template_name": "python-sandbox",
            "replicas": 0,
        }
        pool = Pool.from_dict(data)

        assert pool.replicas == 0


_SAMPLE_SERVICE_URL_DATA = {
    "browser_url": "http://abc123--3000.svc.example.com/_svc/auth?token=jwt",
    "service_url": "http://abc123--3000.svc.example.com/",
    "token": "jwt-token-value",
    "expires_at": "2026-04-01T12:10:00Z",
}


class TestServiceURL:
    """Tests for ServiceURL."""

    def test_from_dict(self):
        """Test creating from API response dict."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)

        assert svc.browser_url == _SAMPLE_SERVICE_URL_DATA["browser_url"]
        assert svc.service_url == _SAMPLE_SERVICE_URL_DATA["service_url"]
        assert svc.token == "jwt-token-value"
        assert svc.expires_at == "2026-04-01T12:10:00Z"

    def test_repr(self):
        """Test repr contains useful fields."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        r = repr(svc)
        assert "ServiceURL" in r
        assert "svc.example.com" in r

    def test_no_refresh_without_refresher(self):
        """Test that properties return stale values without a refresher."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        assert svc._should_refresh() is False
        assert svc.token == "jwt-token-value"

    def test_no_refresh_when_token_fresh(self):
        """Test that refresher is NOT called when token is far from expiry."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": future}
        refresher = MagicMock()
        svc = ServiceURL.from_dict(data, _refresher=refresher)

        _ = svc.token
        refresher.assert_not_called()

    def test_refresh_when_token_near_expiry(self):
        """Test that refresher IS called when token is within the 30s margin."""
        near_expiry = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": near_expiry}

        fresh_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        fresh_svc = ServiceURL(
            browser_url="http://new-browser-url",
            service_url="http://new-service-url/",
            token="new-token",
            expires_at=fresh_future,
        )
        refresher = MagicMock(return_value=fresh_svc)
        svc = ServiceURL.from_dict(data, _refresher=refresher)

        token = svc.token
        refresher.assert_called_once()
        assert token == "new-token"
        assert svc._service_url == "http://new-service-url/"

    def test_no_refresh_just_outside_margin(self):
        """Test that refresher is NOT called when remaining > 30s."""
        just_outside = (datetime.now(timezone.utc) + timedelta(seconds=35)).isoformat()
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": just_outside}
        refresher = MagicMock()
        svc = ServiceURL.from_dict(data, _refresher=refresher)

        _ = svc.token
        refresher.assert_not_called()

    def test_refresh_when_token_expired(self):
        """Test that refresher is called when token is already past expiry."""
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": past}

        fresh_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        fresh_svc = ServiceURL(
            browser_url="b", service_url="s", token="t", expires_at=fresh_future
        )
        refresher = MagicMock(return_value=fresh_svc)
        svc = ServiceURL.from_dict(data, _refresher=refresher)

        _ = svc.browser_url
        refresher.assert_called_once()

    def test_http_get_injects_header(self):
        """Test .get() injects the auth header."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        with patch("langsmith.sandbox._models.httpx.request") as mock_req:
            mock_req.return_value = MagicMock(status_code=200)
            svc.get("/api/data")

            mock_req.assert_called_once()
            call_kwargs = mock_req.call_args
            assert call_kwargs[0][0] == "GET"
            assert "/api/data" in call_kwargs[0][1]
            assert (
                call_kwargs[1]["headers"]["X-Langsmith-Sandbox-Service-Token"]
                == "jwt-token-value"
            )

    def test_http_post_injects_header(self):
        """Test .post() injects the auth header."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        with patch("langsmith.sandbox._models.httpx.request") as mock_req:
            mock_req.return_value = MagicMock(status_code=201)
            svc.post("/api/submit", json={"key": "val"})

            call_kwargs = mock_req.call_args
            assert call_kwargs[0][0] == "POST"
            assert (
                call_kwargs[1]["headers"]["X-Langsmith-Sandbox-Service-Token"]
                == "jwt-token-value"
            )

    def test_request_url_construction(self):
        """Test URL construction joins service_url and path correctly."""
        svc = ServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        with patch("langsmith.sandbox._models.httpx.request") as mock_req:
            mock_req.return_value = MagicMock(status_code=200)
            svc.get("/api/data")
            url = mock_req.call_args[0][1]
            assert url == "http://abc123--3000.svc.example.com/api/data"

    def test_expires_at_without_timezone_treated_as_utc(self):
        """Test expires_at without timezone info is treated as UTC."""
        near_expiry = (datetime.now(timezone.utc) + timedelta(seconds=10)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": near_expiry}

        fresh_svc = ServiceURL(
            browser_url="b",
            service_url="s",
            token="t",
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        refresher = MagicMock(return_value=fresh_svc)
        svc = ServiceURL.from_dict(data, _refresher=refresher)

        _ = svc.token
        refresher.assert_called_once()


class TestAsyncServiceURL:
    """Tests for AsyncServiceURL."""

    def test_from_dict(self):
        """Test creating from API response dict."""
        svc = AsyncServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)

        assert svc.token == "jwt-token-value"
        assert svc.service_url == _SAMPLE_SERVICE_URL_DATA["service_url"]
        assert svc.browser_url == _SAMPLE_SERVICE_URL_DATA["browser_url"]
        assert svc.expires_at == "2026-04-01T12:10:00Z"

    def test_repr(self):
        """Test repr contains useful fields."""
        svc = AsyncServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        r = repr(svc)
        assert "AsyncServiceURL" in r
        assert "svc.example.com" in r

    def test_no_refresh_without_refresher(self):
        """Test _should_refresh is False without a refresher."""
        svc = AsyncServiceURL.from_dict(_SAMPLE_SERVICE_URL_DATA)
        assert svc._should_refresh() is False

    async def test_async_get_token_refreshes(self):
        """Test async get_token() triggers refresh within the 30s margin."""
        near_expiry = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        data = {**_SAMPLE_SERVICE_URL_DATA, "expires_at": near_expiry}

        fresh_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        fresh_svc = AsyncServiceURL(
            browser_url="b",
            service_url="s",
            token="new-async-token",
            expires_at=fresh_future,
        )

        async def mock_refresher() -> AsyncServiceURL:
            return fresh_svc

        svc = AsyncServiceURL.from_dict(data, _refresher=mock_refresher)
        token = await svc.get_token()
        assert token == "new-async-token"
