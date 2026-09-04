# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Required, TypedDict

__all__ = ["SnapshotCreateParams"]


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

    tag: str
    """mutable Docker-style tag; defaults to "latest" """
