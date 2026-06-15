"""Type definitions for sandbox mount configurations."""

from __future__ import annotations

from typing import Literal, TypedDict, Union


class MountCacheConfig(TypedDict, total=False):
    """Optional cache configuration shared by all sandbox mounts."""

    max_size_bytes: int
    writeback_seconds: int


class MountSpecBase(TypedDict, total=False):
    """Optional fields shared by all sandbox mount specifications."""

    read_only: bool
    cache: MountCacheConfig


class S3MountConfigRequired(TypedDict):
    """Required S3 configuration for a sandbox mount."""

    endpoint_url: str
    region: str
    bucket: str


class S3MountConfig(S3MountConfigRequired, total=False):
    """S3 configuration for a sandbox mount."""

    prefix: str
    path_style: bool


class S3MountSpec(MountSpecBase):
    """S3-backed sandbox mount specification."""

    id: str
    type: Literal["s3"]
    mount_path: str
    s3: S3MountConfig


class GCSMountConfigRequired(TypedDict):
    """Required GCS configuration for a sandbox mount."""

    bucket: str


class GCSMountConfig(GCSMountConfigRequired, total=False):
    """GCS configuration for a sandbox mount."""

    prefix: str


class GCSMountSpec(MountSpecBase):
    """GCS-backed sandbox mount specification."""

    id: str
    type: Literal["gcs"]
    mount_path: str
    gcs: GCSMountConfig


SandboxMount = Union[S3MountSpec, GCSMountSpec]
