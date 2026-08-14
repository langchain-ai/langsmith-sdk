# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Required, TypedDict

__all__ = ["SnapshotCreateParams"]


class SnapshotCreateParams(TypedDict, total=False):
    docker_image: Required[str]

    fs_capacity_bytes: Required[int]

    name: Required[str]

    labels: Dict[str, str]
    """
    Labels seed the snapshot's labels, overriding any label of the same key derived
    from the Docker image.
    """

    registry_id: str
