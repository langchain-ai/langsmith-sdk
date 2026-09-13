# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from ..._types import SequenceNotStr

__all__ = ["BoxListParams"]


class BoxListParams(TypedDict, total=False):
    created_by: str
    """Filter by creator identity. Only 'me' is supported."""

    cursor: str
    """Opaque pagination cursor from a prior response's next_cursor"""

    label: SequenceNotStr[str]
    """Filter by label.

    Repeatable; all must match. Use 'key' to match on key presence or 'key=value'
    for equality.
    """

    limit: int
    """Deprecated: use page_size. Maximum number of results"""

    name_contains: str
    """Filter by name substring"""

    offset: int
    """Deprecated: use cursor. Pagination offset"""

    page_size: int
    """Number of results per page"""

    sort_by: str
    """
    Sort column (name, status, created_at, stopped_at, idle_ttl_seconds,
    delete_after_stop_seconds)
    """

    sort_direction: str
    """Deprecated: use sort_order. Sort direction (asc, desc)"""

    sort_order: str
    """Sort direction (asc, desc)"""

    status: str
    """Filter by status (provisioning, ready, failed, stopped, deleting)"""
