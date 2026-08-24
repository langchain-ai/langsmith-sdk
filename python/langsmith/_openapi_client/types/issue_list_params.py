# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Iterable
from typing_extensions import Literal, TypedDict

__all__ = ["IssueListParams"]


class IssueListParams(TypedDict, total=False):
    activity: List[Literal["fixing", "watching", "recurred"]]
    """Filter by Engine activity (repeatable; OR semantics)"""

    limit: int
    """Page size (positive integer; defaults to 50, capped at 500)"""

    offset: int
    """Page offset (non-negative integer; at most 100000)"""

    session_id: str
    """Filter by session ID (UUID)"""

    session_name: str
    """Filter by session name (exact match)"""

    severity: Literal[0, 1, 2, 3]
    """Filter by severity"""

    severity_exact: Iterable[Literal[0, 1, 2, 3]]
    """Filter by exact severity (repeatable; OR semantics)"""

    sort_by: Literal["default", "created_at", "updated_at", "last_seen", "last_updated", "trace_count", "severity"]
    """Sort field"""

    status: Literal["open", "fixing", "watching", "completed", "ignored"]
    """Filter by status"""

    status_first: bool
    """Group results by issue lifecycle status before applying sort_by"""

    tag: str
    """Filter by tag (exact match)"""

    trace_id: str
    """Return only issues with a linked run in this trace"""

    updated_at: str
    """Return only issues updated at or after this RFC3339 timestamp"""
