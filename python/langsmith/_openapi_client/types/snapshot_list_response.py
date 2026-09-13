# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .snapshot_response import SnapshotResponse

__all__ = ["SnapshotListResponse"]


class SnapshotListResponse(BaseModel):
    items: Optional[List[SnapshotResponse]] = None
    """This page of snapshots."""

    next_cursor: Optional[str] = None
    """Cursor for the next page, or null on the last page.

    A non-null value is the only signal that more pages exist. Treat it as opaque.
    """

    offset: Optional[int] = None
    """Deprecated: use next_cursor.

    Offset to request for the next page, or 0 when no pages remain.
    """

    snapshots: Optional[List[SnapshotResponse]] = None
    """Deprecated: use items. Duplicates items."""
