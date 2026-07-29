# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List
from typing_extensions import Literal, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RunQueryParams"]


class RunQueryParams(TypedDict, total=False):
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
            "INPUTS_PREVIEW",
            "OUTPUTS_PREVIEW",
            "PARENT_RUN_ID",
            "PARENT_RUN_IDS",
            "PROJECT_ID",
            "TRACE_ID",
            "THREAD_ID",
            "DOTTED_ORDER",
            "IS_ROOT",
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
            "THREAD_EVALUATION_TIME",
            "FEEDBACK_STATS",
        ]
    ]
    """`selects` lists which public run properties to include on each returned run."""

    accept: Annotated[str, PropertyInfo(alias="Accept")]
