# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from ..._types import SequenceNotStr

__all__ = ["SnapshotListParams"]


class SnapshotListParams(TypedDict, total=False):
    created_by: str
    """Filter by creator identity. Only 'me' is supported."""

    label: SequenceNotStr[str]
    """Filter by label.

    Repeatable; all must match. Use 'key' to match on key presence or 'key=value'
    for equality.
    """

    limit: int
    """Maximum number of results"""

    name_contains: str
    """Filter by name substring"""

    offset: int
    """Pagination offset"""

    sort_by: str
    """Sort column (name, status, created_at)"""

    sort_direction: str
    """Sort direction (asc, desc)"""

    status: str
    """Filter by status (building, ready, failed, deleting)"""
