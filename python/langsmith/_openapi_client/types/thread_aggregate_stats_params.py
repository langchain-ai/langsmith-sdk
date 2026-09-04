# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["ThreadAggregateStatsParams"]


class ThreadAggregateStatsParams(TypedDict, total=False):
    project_id: Required[str]
    """`project_id` is the tracing project UUID."""

    select: Required[
        List[
            Literal[
                "THREAD_COUNT",
                "TRACE_COUNT",
                "TOTAL_TOKENS",
                "TOTAL_COST",
                "ERROR_RATE",
                "STREAMING_RATE",
                "LATENCY_P50",
                "LATENCY_P99",
                "MEDIAN_TOKENS",
                "FIRST_TOKEN_P50",
                "FIRST_TOKEN_P99",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "PROMPT_COST",
                "COMPLETION_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "THREAD_FEEDBACK_STATS",
            ]
        ]
    ]
    """`select` lists the aggregate statistics to compute and return.

    At least one value is required.
    """

    filter: str
    """
    `filter` is a deprecated, unscoped LangSmith filter expression evaluated against
    trace root runs. Kept for compatibility with deployments that serve this
    endpoint via the legacy ClickHouse backend (no SmithDB query service
    configured); prefer `trace_filter`, `tree_filter`, or `thread_filter` otherwise,
    since those require SmithDB.
    """

    max_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `max_start_time` is the exclusive upper bound on thread activity (RFC3339
    date-time). Defaults to now (UTC) when omitted.
    """

    min_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `min_start_time` is the inclusive lower bound on thread activity (RFC3339
    date-time). Defaults to 1 day before now (UTC) when omitted.
    """

    thread_filter: str
    """
    `thread_filter` narrows eligible threads using a LangSmith filter expression
    evaluated against the complete thread summary.
    """

    trace_filter: str
    """
    `trace_filter` narrows eligible threads to those containing a trace whose root
    run matches this LangSmith filter expression.
    """

    tree_filter: str
    """
    `tree_filter` narrows eligible threads to those containing a matching run
    anywhere in a trace tree.
    """
