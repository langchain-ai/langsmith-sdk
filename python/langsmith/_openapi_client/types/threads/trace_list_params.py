# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List
from typing_extensions import Literal, Required, TypedDict

__all__ = ["TraceListParams"]


class TraceListParams(TypedDict, total=False):
    project_id: Required[str]
    """`project_id` is the tracing project UUID (required)."""

    cursor: str
    """`cursor` is the opaque string from a previous response's `next_cursor`.

    Omit on the first request; pass the returned cursor to fetch the next page.
    """

    filter: str
    """
    `filter` narrows which traces are returned for this thread, using a LangSmith
    filter expression evaluated against each root trace run. For example: eq(status,
    "success") or has(tags, "production"). See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    page_size: int
    """`page_size` is the maximum number of traces to return in this response.

    Defaults to 20 when omitted; must be between 1 and 100 inclusive when set.
    """

    selects: List[
        Literal[
            "THREAD_ID",
            "TRACE_ID",
            "OP",
            "PROMPT_TOKENS",
            "COMPLETION_TOKENS",
            "TOTAL_TOKENS",
            "START_TIME",
            "END_TIME",
            "LATENCY",
            "FIRST_TOKEN_TIME",
            "INPUTS_PREVIEW",
            "OUTPUTS_PREVIEW",
            "PROMPT_COST",
            "COMPLETION_COST",
            "TOTAL_COST",
            "PROMPT_TOKEN_DETAILS",
            "COMPLETION_TOKEN_DETAILS",
            "PROMPT_COST_DETAILS",
            "COMPLETION_COST_DETAILS",
            "NAME",
            "ERROR_PREVIEW",
        ]
    ]
    """
    `selects` lists which properties to include on each returned trace (repeatable
    query parameter). Accepts any value of the `ThreadTraceSelectField` enum.
    Properties not listed are omitted from each trace object; `trace_id` is always
    returned.
    """
