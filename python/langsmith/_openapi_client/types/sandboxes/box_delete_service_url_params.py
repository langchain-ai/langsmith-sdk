# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["BoxDeleteServiceURLParams"]


class BoxDeleteServiceURLParams(TypedDict, total=False):
    port: int
    """Port to stop sharing. Omit to stop sharing every port."""
