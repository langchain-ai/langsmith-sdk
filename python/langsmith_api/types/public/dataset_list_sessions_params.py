# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from ..._types import SequenceNotStr
from ..session_sortable_columns import SessionSortableColumns

__all__ = ["DatasetListSessionsParams"]


class DatasetListSessionsParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    dataset_version: Optional[str]

    facets: bool

    limit: int

    name: Optional[str]

    name_contains: Optional[str]

    offset: int

    sort_by: SessionSortableColumns

    sort_by_desc: bool

    sort_by_feedback_key: Optional[str]

    accept: str
