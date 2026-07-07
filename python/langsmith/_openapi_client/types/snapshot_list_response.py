# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .snapshot_response import SnapshotResponse

__all__ = ["SnapshotListResponse"]


class SnapshotListResponse(BaseModel):
    offset: Optional[int] = None

    snapshots: Optional[List[SnapshotResponse]] = None
