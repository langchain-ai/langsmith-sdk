"""Tests for sandbox data models."""

from langsmith.sandbox import (
    ExecutionResult,
    Pool,
    ResourceSpec,
    SandboxTemplate,
    Volume,
    VolumeMountSpec,
)


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
