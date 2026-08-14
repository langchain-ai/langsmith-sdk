# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional

from .._models import BaseModel

__all__ = ["SnapshotResponse"]


class SnapshotResponse(BaseModel):
    id: Optional[str] = None

    created_at: Optional[str] = None

    created_by: Optional[str] = None

    docker_image: Optional[str] = None

    fs_capacity_bytes: Optional[int] = None

    fs_used_bytes: Optional[int] = None

    image_digest: Optional[str] = None

    labels: Optional[Dict[str, str]] = None

    memory_snapshot_size_bytes: Optional[int] = None
    """
    MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
    state. A non-nil value is the canonical signal that this snapshot can
    warm-restore from memory; nil means rootfs only.
    """

    name: Optional[str] = None

    registry_id: Optional[str] = None

    source_sandbox_id: Optional[str] = None

    status: Optional[str] = None

    status_message: Optional[str] = None

    updated_at: Optional[str] = None
