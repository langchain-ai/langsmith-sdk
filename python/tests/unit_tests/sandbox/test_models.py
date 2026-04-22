"""Tests for sandbox data models."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from langsmith.sandbox import (
    AsyncServiceURL,
    ExecutionResult,
    OutputChunk,
    ResourceStatus,
    ServiceURL,
    Snapshot,
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


class TestSnapshot:
    """Tests for Snapshot model."""

    def test_from_dict_full(self):
        """Test creating from full API response dict."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440099",
            "name": "my-python-env",
            "status": "ready",
            "fs_capacity_bytes": 4294967296,
            "docker_image": "python:3.12-slim",
            "image_digest": "sha256:abc123",
            "source_sandbox_id": None,
            "status_message": None,
            "fs_used_bytes": 1073741824,
            "created_by": "user@example.com",
            "registry_id": "reg-123",
            "created_at": "2025-06-01T00:00:00Z",
            "updated_at": "2025-06-01T00:05:00Z",
        }
        snap = Snapshot.from_dict(data)

        assert snap.id == "550e8400-e29b-41d4-a716-446655440099"
        assert snap.name == "my-python-env"
        assert snap.status == "ready"
        assert snap.fs_capacity_bytes == 4294967296
        assert snap.docker_image == "python:3.12-slim"
        assert snap.image_digest == "sha256:abc123"
        assert snap.fs_used_bytes == 1073741824
        assert snap.created_by == "user@example.com"
        assert snap.registry_id == "reg-123"
        assert snap.created_at == "2025-06-01T00:00:00Z"
        assert snap.updated_at == "2025-06-01T00:05:00Z"

    def test_from_dict_minimal(self):
        """Test creating from minimal dict with defaults."""
        data = {
            "id": "snap-1",
            "name": "test",
            "status": "building",
            "fs_capacity_bytes": 1073741824,
        }
        snap = Snapshot.from_dict(data)

        assert snap.id == "snap-1"
        assert snap.name == "test"
        assert snap.status == "building"
        assert snap.fs_capacity_bytes == 1073741824
        assert snap.docker_image is None
        assert snap.image_digest is None
        assert snap.source_sandbox_id is None
        assert snap.status_message is None
        assert snap.fs_used_bytes is None
        assert snap.created_by is None

    def test_from_dict_capture_snapshot(self):
        """Test creating from a capture (has source_sandbox_id, no docker_image)."""
        data = {
            "id": "snap-2",
            "name": "captured",
            "status": "ready",
            "fs_capacity_bytes": 4294967296,
            "source_sandbox_id": "box-abc",
        }
        snap = Snapshot.from_dict(data)

        assert snap.source_sandbox_id == "box-abc"
        assert snap.docker_image is None
