# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from .._types import SequenceNotStr

__all__ = ["OnlineEvaluatorListParams"]


class OnlineEvaluatorListParams(TypedDict, total=False):
    feedback_key: str
    """Filter by feedback key"""

    limit: int
    """Maximum number of results (1-100)"""

    name_contains: str
    """Filter by name substring (also searches creator names)"""

    offset: int
    """Offset for pagination"""

    resource_id: SequenceNotStr[str]
    """Filter by resource IDs"""

    sort_by: str
    """Field to sort by"""

    sort_by_desc: bool
    """Sort in descending order"""

    tag_value_id: SequenceNotStr[str]
    """Filter by tag value IDs"""

    type: str
    """Filter by evaluator type"""
