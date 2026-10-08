# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["BoxCreateSnapshotParams", "RunConfig"]


class BoxCreateSnapshotParams(TypedDict, total=False):
    body_name: Required[Annotated[str, PropertyInfo(alias="name")]]

    checkpoint: str
    """if omitted, creates a fresh checkpoint from the running VM"""

    description: str
    """
    Description says what this snapshot's image can do, so a caller can hand it to
    an agent as a capability summary. At most 1024 characters.
    """

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

    labels: Dict[str, str]
    """Labels seed the captured snapshot's labels."""

    run_config: RunConfig
    """
    RunConfig overrides the runtime configuration the snapshot carries: for a
    docker_image export, the image's USER, WORKDIR and ENV; for a capture of the
    running VM, the sandbox's own. user and work_dir replace, env_vars merge.
    """

    tag: str
    """mutable Docker-style tag; defaults to "latest" """


class RunConfig(TypedDict, total=False):
    """
    RunConfig overrides the runtime configuration the snapshot carries: for a
    docker_image export, the image's USER, WORKDIR and ENV; for a capture of
    the running VM, the sandbox's own. user and work_dir replace, env_vars
    merge.
    """

    env_vars: Dict[str, str]

    user: str

    work_dir: str
