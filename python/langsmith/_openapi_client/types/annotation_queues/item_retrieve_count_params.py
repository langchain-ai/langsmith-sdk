# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["ItemRetrieveCountParams"]


class ItemRetrieveCountParams(TypedDict, total=False):
    status: Required[str]
    """Count bucket: all, needs_my_review, needs_others_review, or archived."""

    end_time: str
    """Exclusive upper bound for archived item timestamp"""

    start_time: str
    """Exclusive lower bound for archived item timestamp"""
