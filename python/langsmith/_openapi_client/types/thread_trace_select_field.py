# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal, TypeAlias

__all__ = ["ThreadTraceSelectField"]

ThreadTraceSelectField: TypeAlias = Literal[
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
