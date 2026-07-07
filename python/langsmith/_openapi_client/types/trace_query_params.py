# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["TraceQueryParams"]


class TraceQueryParams(TypedDict, total=False):
    cursor: str
    """`cursor` is the opaque string returned in a previous response's `next_cursor`."""

    max_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `max_start_time` is the exclusive upper bound for the root-run start time scan
    (RFC3339). Defaults to the request time when omitted.
    """

    min_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """
    `min_start_time` is the inclusive lower bound for the root-run start time scan
    (RFC3339). Defaults to 24 hours before the request when omitted.
    """

    page_size: int
    """`page_size` is the maximum number of traces to return per page.

    Defaults to 20; must be between 1 and 100 when set.
    """

    project_id: str
    """`project_id` is the UUID of the tracing project that owns the traces. Required."""

    selects: List[
        Literal[
            "ID",
            "NAME",
            "RUN_TYPE",
            "STATUS",
            "START_TIME",
            "END_TIME",
            "LATENCY_SECONDS",
            "FIRST_TOKEN_TIME",
            "ERROR",
            "ERROR_PREVIEW",
            "EXTRA",
            "METADATA",
            "EVENTS",
            "INPUTS",
            "INPUTS_PREVIEW",
            "OUTPUTS",
            "OUTPUTS_PREVIEW",
            "MANIFEST",
            "PARENT_RUN_IDS",
            "PROJECT_ID",
            "TRACE_ID",
            "THREAD_ID",
            "DOTTED_ORDER",
            "IS_ROOT",
            "REFERENCE_EXAMPLE_ID",
            "REFERENCE_DATASET_ID",
            "TOTAL_TOKENS",
            "PROMPT_TOKENS",
            "COMPLETION_TOKENS",
            "TOTAL_COST",
            "PROMPT_COST",
            "COMPLETION_COST",
            "PROMPT_TOKEN_DETAILS",
            "COMPLETION_TOKEN_DETAILS",
            "PROMPT_COST_DETAILS",
            "COMPLETION_COST_DETAILS",
            "PRICE_MODEL_ID",
            "TAGS",
            "APP_PATH",
            "ATTACHMENTS",
            "THREAD_EVALUATION_TIME",
            "IS_IN_DATASET",
            "SHARE_URL",
            "FEEDBACK_STATS",
        ]
    ]
    """`selects` lists which properties to include on each returned trace.

    Properties listed here are routed to the appropriate sub-object on each item:
    `total_tokens`, `total_cost`, and `first_token_time` appear under
    `trace_aggregates`; everything else appears under `root_run`. If omitted, only
    `id` is returned on `root_run`.
    """

    trace_filter: str
    """
    `trace_filter` narrows results to traces whose root run matches this LangSmith
    filter expression. This filter targets root runs only — `is_root = true` is
    implied. See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    trace_ids: SequenceNotStr[str]
    """`trace_ids` is an optional fast-path restriction to a known set of trace UUIDs.

    Equivalent in result to including each UUID in a `trace_filter`, but more
    efficient at scale.
    """

    tree_filter: str
    """
    `tree_filter` narrows results to traces containing at least one run anywhere in
    the run tree (root or descendant) that matches this LangSmith filter expression.
    """
