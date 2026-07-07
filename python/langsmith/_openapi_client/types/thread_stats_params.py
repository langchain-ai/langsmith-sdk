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
