# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = [
    "ThreadTraceListItem",
    "CompletionCostDetails",
    "CompletionTokenDetails",
    "PromptCostDetails",
    "PromptTokenDetails",
]


class CompletionCostDetails(BaseModel):
    """
    `completion_cost_details` is the USD cost breakdown for completion-side categories; per-category values are under `raw`. Omitted unless included in `selects`.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class CompletionTokenDetails(BaseModel):
    """
    `completion_token_details` is the completion-side token breakdown by category; per-category counts are under `raw`. Omitted unless included in `selects`.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its completion-token count."""


class PromptCostDetails(BaseModel):
    """
    `prompt_cost_details` is the USD cost breakdown for prompt-side categories; per-category values are under `raw`. Omitted unless included in `selects`.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class PromptTokenDetails(BaseModel):
    """
    `prompt_token_details` is the prompt-side token breakdown by category; per-category counts are under nested `raw`. Omitted unless included in `selects`.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its prompt-token count."""


class ThreadTraceListItem(BaseModel):
    completion_cost: Optional[float] = None
    """`completion_cost` is the estimated USD cost for the completion.

    Omitted unless included in `selects`.
    """

    completion_cost_details: Optional[CompletionCostDetails] = None
    """
    `completion_cost_details` is the USD cost breakdown for completion-side
    categories; per-category values are under `raw`. Omitted unless included in
    `selects`.
    """

    completion_token_details: Optional[CompletionTokenDetails] = None
    """
    `completion_token_details` is the completion-side token breakdown by category;
    per-category counts are under `raw`. Omitted unless included in `selects`.
    """

    completion_tokens: Optional[int] = None
    """`completion_tokens` is the completion-side token count.

    Omitted unless included in `selects`.
    """

    end_time: Optional[datetime] = None
    """`end_time` is when the root run ended (RFC3339 date-time).

    JSON null if the run is still in progress. Omitted unless included in `selects`.
    """

    error_preview: Optional[str] = None
    """`error_preview` is a short error summary when the run failed.

    Omitted unless included in `selects`.
    """

    first_token_time: Optional[datetime] = None
    """
    `first_token_time` is when the first output token was produced (RFC3339
    date-time), for streamed runs when that metadata exists. Omitted unless included
    in `selects`.
    """

    inputs_preview: Optional[str] = None
    """`inputs_preview` is a truncated text preview of inputs.

    Omitted unless included in `selects`.
    """

    latency: Optional[float] = None
    """`latency` is wall-clock duration from start to end in seconds.

    Omitted unless included in `selects`.
    """

    name: Optional[str] = None
    """
    `name` is a human-readable label for the root run (for example the model name,
    function name, or step name chosen when the run was traced). Omitted unless
    included in `selects`.
    """

    op: Optional[float] = None
    """`op` is a numeric code identifying the root run's `run_type` (for example LLM
    vs.

    tool vs. chain). Encoded as a number for compatibility with legacy clients;
    prefer the string `run_type` on `RunResponse` when available. Omitted unless
    included in `selects`.
    """

    outputs_preview: Optional[str] = None
    """`outputs_preview` is a truncated text preview of outputs.

    Omitted unless included in `selects`.
    """

    prompt_cost: Optional[float] = None
    """`prompt_cost` is the estimated USD cost for the prompt.

    Omitted unless included in `selects`.
    """

    prompt_cost_details: Optional[PromptCostDetails] = None
    """
    `prompt_cost_details` is the USD cost breakdown for prompt-side categories;
    per-category values are under `raw`. Omitted unless included in `selects`.
    """

    prompt_token_details: Optional[PromptTokenDetails] = None
    """
    `prompt_token_details` is the prompt-side token breakdown by category;
    per-category counts are under nested `raw`. Omitted unless included in
    `selects`.
    """

    prompt_tokens: Optional[int] = None
    """`prompt_tokens` is the prompt-side token count.

    Omitted unless included in `selects`.
    """

    start_time: Optional[datetime] = None
    """`start_time` is when the trace started (RFC3339 date-time).

    Omitted unless included in `selects`.
    """

    thread_id: Optional[str] = None
    """`thread_id` is the conversation thread UUID that contains this trace.

    Matches the `thread_id` path parameter of the request. Omitted unless included
    in `selects`.
    """

    total_cost: Optional[float] = None
    """`total_cost` is the estimated total USD cost for the root run.

    Omitted unless included in `selects`.
    """

    total_tokens: Optional[int] = None
    """`total_tokens` is the total token count (prompt plus completion).

    Omitted unless included in `selects`.
    """

    trace_id: Optional[str] = None
    """`trace_id` is the UUID of this trace (the root run). Always present."""
