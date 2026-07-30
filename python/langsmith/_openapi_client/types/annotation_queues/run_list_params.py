# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, TypedDict

__all__ = ["RunListParams"]


class RunListParams(TypedDict, total=False):
    archived: Optional[bool]

    include_stats: Optional[bool]

    limit: int

    offset: int

    status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]]
