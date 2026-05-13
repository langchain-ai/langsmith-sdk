# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .session_sortable_columns import SessionSortableColumns

__all__ = ["SessionListParams"]


class SessionListParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    dataset_version: Optional[str]

    facets: bool

    filter: Optional[str]

    include_stats: bool

    limit: int

    metadata: Optional[str]

    name: Optional[str]

    name_contains: Optional[str]

    offset: int

    reference_dataset: Optional[SequenceNotStr[str]]

    reference_free: Optional[bool]

    sort_by: SessionSortableColumns

    sort_by_desc: bool

    sort_by_feedback_key: Optional[str]

    stats_filter: Optional[str]

    stats_select: Optional[SequenceNotStr[str]]

    stats_start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    tag_value_id: Optional[SequenceNotStr[str]]

    use_approx_stats: bool

    accept: str
