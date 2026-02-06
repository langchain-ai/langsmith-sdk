"""Data models for the sandbox client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExecutionResult:
    """Result of executing a command in a sandbox."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        """Return True if the command exited with code 0."""
        return self.exit_code == 0


@dataclass
class ResourceSpec:
    """Resource specification for a sandbox."""

    cpu: str = "500m"
    memory: str = "512Mi"
    storage: Optional[str] = None


@dataclass
class Volume:
    """Represents a persistent volume.

    Volumes are persistent storage that can be mounted in sandboxes.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    size: str
    storage_class: str
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Volume:
        """Create a Volume from API response dict."""
        return cls(
            name=data.get("name", ""),
            size=data.get("size", "unknown"),
            storage_class=data.get("storage_class", "default"),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class VolumeMountSpec:
    """Specification for mounting a volume in a sandbox template."""

    volume_name: str
    mount_path: str


@dataclass
class SandboxTemplate:
    """Represents a SandboxTemplate.

    Templates define the image, resource limits, and volume mounts for sandboxes.
    All other container details are handled by the server with secure defaults.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    image: str
    resources: ResourceSpec
    volume_mounts: list[VolumeMountSpec] = field(default_factory=list)
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxTemplate:
        """Create a SandboxTemplate from API response dict."""
        resources_data = data.get("resources", {})
        volume_mounts_data = data.get("volume_mounts", [])
        return cls(
            name=data.get("name", ""),
            image=data.get("image", "unknown"),
            resources=ResourceSpec(
                cpu=resources_data.get("cpu", "500m"),
                memory=resources_data.get("memory", "512Mi"),
                storage=resources_data.get("storage"),
            ),
            volume_mounts=[
                VolumeMountSpec(
                    volume_name=vm.get("volume_name", ""),
                    mount_path=vm.get("mount_path", ""),
                )
                for vm in volume_mounts_data
            ],
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Pool:
    """Represents a Sandbox Pool for pre-provisioned sandboxes.

    Pools pre-provision sandboxes from a template for faster startup.
    Instead of waiting for a new sandbox to be created, sandboxes can
    be served from a pre-warmed pool.

    Note: Templates with volume mounts cannot be used in pools.

    Attributes:
        id: Unique identifier (UUID). Remains constant even if name changes.
            May be None for resources created before ID support was added.
        name: Display name (can be updated).
    """

    name: str
    template_name: str
    replicas: int  # Desired replicas
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pool:
        """Create a Pool from API response dict."""
        return cls(
            name=data.get("name", ""),
            template_name=data.get("template_name", ""),
            replicas=data.get("replicas", 0),
            id=data.get("id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
