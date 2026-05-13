# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["RunQueryParams"]


class RunQueryParams(TypedDict, total=False):
    ai_query: str
    """`ai_query` is a natural-language query to filter runs using AI."""

    cursor: str
    """`cursor` is the opaque string from a previous response's `next_cursor`."""

    filter: str
    """
    `filter` narrows results to runs matching this LangSmith filter expression,
    evaluated against each individual run. For example: and(eq(run_type, "llm"),
    gt(latency, 5)) or eq(status, "error"). See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    has_error: bool
    """
    `has_error` filters to runs that errored (true) or completed without error
    (false).
    """

    ids: SequenceNotStr[str]
    """`ids` optionally limits the request to these run UUIDs."""

    is_root: bool
    """`is_root` returns only root runs (true) or only non-root runs (false)."""

    max_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """`max_start_time` is the upper bound for run `start_time` (RFC3339).

    Defaults to now.
    """

    min_start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
    """`min_start_time` is the lower bound for run `start_time` (RFC3339).

    Defaults to 1 day ago.
    """

    page_size: int
    """`page_size` is the maximum number of runs to return in this response.

    Defaults to 100 when omitted; must be between 1 and 1000 inclusive when set.
    """

    project_ids: SequenceNotStr[str]
    """`project_ids` lists tracing project UUIDs to query."""

    reference_examples: SequenceNotStr[str]
    """
    `reference_examples` optionally limits to runs linked to these dataset example
    UUIDs.
    """

    run_type: Literal["TOOL", "CHAIN", "LLM", "RETRIEVER", "EMBEDDING", "PROMPT", "PARSER"]
    """
    `run_type`, when set, restricts results to runs whose `run_type` equals this
    value.
    """

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
    """`selects` lists which properties to include on each returned run.

    If omitted, only `id` is returned. Properties not listed are omitted from each
    run object.
    """

    sort_order: Literal["ASC", "DESC"]
    """`sort_order` is the sort direction for `start_time` (`ASC` or `DESC`).

    Defaults to `DESC` when omitted. Maps to the SmithDB proto `Order` field.
    """

    trace_filter: str
    """
    `trace_filter` narrows results to runs whose root trace matches this LangSmith
    filter expression. Use this to filter by properties of the trace's root run —
    for example eq(status, "success") to include only traces that completed without
    error. See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    trace_id: str
    """`trace_id` optionally limits results to runs belonging to this trace UUID."""

    tree_filter: str
    """
    `tree_filter` narrows results to runs that belong to a trace containing at least
    one run matching this LangSmith filter expression anywhere in the run tree (not
    just the root). Use this to find runs inside traces that involved a specific
    tool, tag, or model — for example has(tags, "production") or eq(name,
    "my_tool"). See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
    """

    accept: Annotated[str, PropertyInfo(alias="Accept")]
