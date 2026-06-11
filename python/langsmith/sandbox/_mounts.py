"""Type definitions for sandbox mount configurations."""

from __future__ import annotations

from typing import Literal, TypedDict


class S3MountConfigRequired(TypedDict):
    """Required S3 configuration for a sandbox mount."""

    endpoint_url: str
    region: str
    bucket: str


class S3MountConfig(S3MountConfigRequired, total=False):
    """S3 configuration for a sandbox mount."""

    prefix: str
    path_style: bool


class S3MountSpec(TypedDict):
    """S3-backed sandbox mount specification."""

    id: str
    type: Literal["s3"]
    mount_path: str
    s3: S3MountConfig


SandboxMount = S3MountSpec
