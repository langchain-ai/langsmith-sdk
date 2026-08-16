# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

__all__ = ["ItemListParams"]


class ItemListParams(TypedDict, total=False):
    status: Required[Literal["needs_my_review", "needs_others_review", "archived"]]
    """Review section: needs_my_review, needs_others_review, or archived"""

    cursor: str
    """Opaque pagination cursor"""

    direction: Literal["forward", "backward"]
    """Pagination direction. backward requires cursor"""

    item_type: Literal["RUN", "THREAD"]
    """Filter to RUN or THREAD"""

    page_size: int
    """Page size (max 100)"""
