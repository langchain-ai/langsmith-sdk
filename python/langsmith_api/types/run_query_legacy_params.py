# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .run_type_enum import RunTypeEnum
from .runs_filter_data_source_type_enum import RunsFilterDataSourceTypeEnum

__all__ = ["RunQueryLegacyParams"]


class RunQueryLegacyParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    cursor: Optional[str]

    data_source_type: Optional[RunsFilterDataSourceTypeEnum]
    """Enum for run data source types."""

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    error: Optional[bool]

    execution_order: Optional[int]

    filter: Optional[str]

    is_root: Optional[bool]

    limit: int

    order: Literal["asc", "desc"]
    """Enum for run start date order."""

    parent_run: Optional[str]

    query: Optional[str]

    reference_example: Optional[SequenceNotStr[str]]

    run_type: Optional[RunTypeEnum]
    """Enum for run types."""

    search_filter: Optional[str]

    select: List[
        Literal[
            "id",
            "name",
            "run_type",
            "start_time",
            "end_time",
            "status",
            "error",
            "extra",
            "events",
            "inputs",
            "inputs_preview",
            "inputs_s3_urls",
            "inputs_or_signed_url",
            "outputs",
            "outputs_preview",
            "outputs_s3_urls",
            "outputs_or_signed_url",
            "s3_urls",
            "error_or_signed_url",
            "events_or_signed_url",
            "extra_or_signed_url",
            "serialized_or_signed_url",
            "parent_run_id",
            "manifest_id",
            "manifest_s3_id",
            "manifest",
            "session_id",
            "serialized",
            "reference_example_id",
            "reference_dataset_id",
            "total_tokens",
            "prompt_tokens",
            "prompt_token_details",
            "completion_tokens",
            "completion_token_details",
            "total_cost",
            "prompt_cost",
            "prompt_cost_details",
            "completion_cost",
            "completion_cost_details",
            "price_model_id",
            "first_token_time",
            "trace_id",
            "dotted_order",
            "last_queued_at",
            "feedback_stats",
            "child_run_ids",
            "parent_run_ids",
            "tags",
            "in_dataset",
            "app_path",
            "share_token",
            "trace_tier",
            "trace_first_received_at",
            "ttl_seconds",
            "trace_upgrade",
            "thread_id",
            "trace_min_max_start_time",
            "messages",
            "inserted_at",
        ]
    ]

    session: Optional[SequenceNotStr[str]]

    skip_pagination: Optional[bool]

    skip_prev_cursor: bool

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace: Optional[str]

    trace_filter: Optional[str]

    tree_filter: Optional[str]

    use_experimental_search: bool
