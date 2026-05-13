# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RunListParams"]


class RunListParams(TypedDict, total=False):
    max_start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """
    `max_start_time` is the inclusive upper bound for run `start_time` (RFC3339
    date-time).
    """

    min_start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """
    `min_start_time` is the inclusive lower bound for run `start_time` (RFC3339
    date-time).
    """

    project_id: Required[str]
    """`project_id` is the UUID of the tracing project that owns the trace."""

    filter: str
    """
    `filter` narrows which runs within this trace are returned, using a LangSmith
    filter expression evaluated against each run. For example: `eq(run_type, "llm")`
    for LLM runs only, or `eq(status, "error")` for failed runs. See
    https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
    for syntax.
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
    """
    `selects` lists which properties to include on each returned run (repeatable
    query parameter). Accepts any value of the `RunSelectField` enum. If omitted,
    only `id` is returned.
    """

    accept: Annotated[str, PropertyInfo(alias="Accept")]
