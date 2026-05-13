# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .run_type_enum import RunTypeEnum
from .run_stats_group_by_param import RunStatsGroupByParam
from .runs_filter_data_source_type_enum import RunsFilterDataSourceTypeEnum

__all__ = ["RunStatsParams"]


class RunStatsParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    data_source_type: Optional[RunsFilterDataSourceTypeEnum]
    """Enum for run data source types."""

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    error: Optional[bool]

    execution_order: Optional[int]

    filter: Optional[str]

    group_by: Optional[RunStatsGroupByParam]
    """Group by param for run stats."""

    groups: Optional[SequenceNotStr[Optional[str]]]

    is_root: Optional[bool]

    parent_run: Optional[str]

    query: Optional[str]

    reference_example: Optional[SequenceNotStr[str]]

    run_type: Optional[RunTypeEnum]
    """Enum for run types."""

    search_filter: Optional[str]

    select: Optional[
        List[
            Literal[
                "run_count",
                "latency_p50",
                "latency_p99",
                "latency_avg",
                "first_token_p50",
                "first_token_p99",
                "total_tokens",
                "prompt_tokens",
                "completion_tokens",
                "median_tokens",
                "completion_tokens_p50",
                "prompt_tokens_p50",
                "tokens_p99",
                "completion_tokens_p99",
                "prompt_tokens_p99",
                "last_run_start_time",
                "feedback_stats",
                "thread_feedback_stats",
                "run_facets",
                "error_rate",
                "streaming_rate",
                "total_cost",
                "prompt_cost",
                "completion_cost",
                "cost_p50",
                "cost_p99",
                "session_feedback_stats",
                "all_run_stats",
                "all_token_stats",
                "prompt_token_details",
                "completion_token_details",
                "prompt_cost_details",
                "completion_cost_details",
            ]
        ]
    ]

    session: Optional[SequenceNotStr[str]]

    skip_pagination: Optional[bool]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace: Optional[str]

    trace_filter: Optional[str]

    tree_filter: Optional[str]

    use_experimental_search: bool
