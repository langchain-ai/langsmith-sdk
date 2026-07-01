# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, TypedDict

__all__ = ["IssueListParams"]


class IssueListParams(TypedDict, total=False):
    limit: int
    """Page size (positive integer; defaults to 50, capped at 500)"""

    offset: int
    """Page offset (non-negative integer)"""

    session_id: str
    """Filter by session ID (UUID)"""

    session_name: str
    """Filter by session name (exact match)"""

    severity: Literal[0, 1, 2, 3]
    """Filter by severity"""

    sort_by: Literal["created_at", "updated_at", "severity"]
    """Sort field"""

    status: Literal["open", "completed", "ignored"]
    """Filter by status"""

    tag: str
    """Filter by tag (exact match)"""

    updated_at: str
    """Return only issues updated at or after this RFC3339 timestamp"""
