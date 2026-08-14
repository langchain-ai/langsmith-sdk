# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List
from typing_extensions import Literal, Required, TypedDict

__all__ = ["ThreadStatsParams"]


class ThreadStatsParams(TypedDict, total=False):
    selects: Required[
        List[
            Literal[
                "TURNS",
                "FIRST_START_TIME",
                "LAST_START_TIME",
                "LAST_END_TIME",
                "LATENCY_P50",
                "LATENCY_P99",
                "PROMPT_TOKENS",
                "PROMPT_COST",
                "COMPLETION_TOKENS",
                "COMPLETION_COST",
                "TOTAL_TOKENS",
                "TOTAL_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "FEEDBACK_STATS",
            ]
        ]
    ]
    """
    `selects` lists which aggregate stats to compute and return (repeatable query
    parameter). At least one value is required. Accepts any value of
    `SingleThreadStatsSelectField`.
    """

    session_id: Required[str]
    """`session_id` is the tracing project (session) UUID (required)."""

    filter: str
    """
    `filter` narrows which of the thread's traces are aggregated, using a LangSmith
    filter expression. For example: lt(start_time, "2025-01-01T00:00:00Z") or
    eq(trace_id, "0190a1b2-c3d4-7ef0-a5b6-6ea3a82e9328"). See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """
