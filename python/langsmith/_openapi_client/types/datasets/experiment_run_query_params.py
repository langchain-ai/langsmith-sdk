# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List
from typing_extensions import Literal, TypedDict

from ..._types import SequenceNotStr

__all__ = ["ExperimentRunQueryParams", "Sort"]


class ExperimentRunQueryParams(TypedDict, total=False):
    comparative_experiment_id: str
    """`comparative_experiment_id` scopes pairwise-annotation feedback (optional)."""

    cursor: str
    """`cursor` is the opaque string from a previous response's `next_cursor`.

    Absent for the first page.
    """

    example_ids: SequenceNotStr[str]
    """
    `example_ids` optionally restricts the page to these dataset example UUIDs (max
    1000).
    """

    experiment_ids: SequenceNotStr[str]
    """`experiment_ids` lists the experiment (tracing session) UUIDs to query.

    Required, non-empty.
    """

    filters: Dict[str, SequenceNotStr[str]]
    """
    `filters` maps a project (session) UUID string to a list of filter expressions
    (optional).
    """

    page_size: int
    """`page_size` is the maximum number of examples to return.

    Defaults to 20, max 100.
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
    """`selects` lists which run properties to include.

    Omitted => only `id`. Tokens mirror /v2/runs/query.
    """

    sort: Sort
    """`sort` controls feedback-score sorting (single project only)."""


class Sort(TypedDict, total=False):
    """`sort` controls feedback-score sorting (single project only)."""

    by: str
    """`by` is the feedback selector, e.g.

    `feedback.correctness` (the `feedback.` prefix is optional).
    """

    order: str
    """`order` is `ASC` or `DESC` (defaults to `DESC`)."""
