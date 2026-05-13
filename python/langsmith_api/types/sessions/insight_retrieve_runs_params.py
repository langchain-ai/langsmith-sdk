# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["InsightRetrieveRunsParams"]


class InsightRetrieveRunsParams(TypedDict, total=False):
    session_id: Required[str]

    attribute_sort_key: Optional[str]

    attribute_sort_order: Optional[Literal["asc", "desc"]]

    cluster_id: Optional[str]

    limit: int

    offset: int
