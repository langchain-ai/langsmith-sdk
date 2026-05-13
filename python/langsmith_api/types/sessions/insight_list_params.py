# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["InsightListParams"]


class InsightListParams(TypedDict, total=False):
    config_id: Optional[str]

    legacy: Optional[bool]

    limit: int

    offset: int
