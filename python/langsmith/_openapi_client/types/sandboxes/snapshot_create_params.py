# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Required, TypedDict

__all__ = ["SnapshotCreateParams", "RunConfig"]


class SnapshotCreateParams(TypedDict, total=False):
    docker_image: Required[str]

    fs_capacity_bytes: Required[int]

    name: Required[str]

    description: str
    """
    Description says what this snapshot's image can do, so a caller can hand it to
    an agent as a capability summary. At most 1024 characters.
    """

    labels: Dict[str, str]
    """
    Labels seed the snapshot's labels, overriding any label of the same key derived
    from the Docker image.
    """

    registry_id: str

    run_config: RunConfig
    """
    RunConfig overrides the runtime configuration taken from the Docker image. Every
    sandbox created from the snapshot runs as the image's USER, in its WORKDIR, with
    its ENV beneath the sandbox's own env_vars; user and work_dir given here replace
    the image's, and env_vars merge over it.
    """

    tag: str
    """mutable Docker-style tag; defaults to "latest" """


class RunConfig(TypedDict, total=False):
    """
    RunConfig overrides the runtime configuration taken from the Docker image.
    Every sandbox created from the snapshot runs as the image's USER, in its
    WORKDIR, with its ENV beneath the sandbox's own env_vars; user and
    work_dir given here replace the image's, and env_vars merge over it.
    """

    env_vars: Dict[str, str]

    user: str

    work_dir: str
