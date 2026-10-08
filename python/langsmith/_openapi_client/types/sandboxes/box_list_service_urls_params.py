# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["BoxListServiceURLsParams"]


class BoxListServiceURLsParams(TypedDict, total=False):
    cursor: str
    """Opaque pagination cursor from a prior response's next_cursor"""

    page_size: int
    """Number of results per page"""
