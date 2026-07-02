# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["BoxCreateSnapshotParams"]


class BoxCreateSnapshotParams(TypedDict, total=False):
    body_name: Required[Annotated[str, PropertyInfo(alias="name")]]

    checkpoint: str
    """if omitted, creates a fresh checkpoint from the running VM"""

    docker_image: str
    """sandbox-local Docker image to export"""

    fs_capacity_bytes: int
    """required for Docker image export unless the sandbox has a capacity"""

    include_memory: bool
    """
    IncludeMemory, when true, captures a full VM memory snapshot alongside the
    filesystem clone. Only honored when the sandbox is running AND Checkpoint is
    omitted (i.e. a fresh in-VM checkpoint is requested). Defaults to false to keep
    snapshots small unless memory restore is explicitly desired.
    """
