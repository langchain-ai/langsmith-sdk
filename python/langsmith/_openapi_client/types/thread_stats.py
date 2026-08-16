# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = [
    "ThreadStats",
    "CompletionCostDetails",
    "CompletionTokenDetails",
    "FeedbackStats",
    "PromptCostDetails",
    "PromptTokenDetails",
]


class CompletionCostDetails(BaseModel):
    """
    `completion_cost_details` is the per-sub-category sum of completion cost details across the thread. Populated when `COMPLETION_COST_DETAILS` is selected.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class CompletionTokenDetails(BaseModel):
    """
    `completion_token_details` is the per-sub-category sum of completion token details across the thread. Populated when `COMPLETION_TOKEN_DETAILS` is selected.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its completion-token count."""


class FeedbackStats(BaseModel):
    avg: Optional[float] = None
    """
    `avg` is the arithmetic mean of numeric feedback scores for this key on the run,
    or `null` when no numeric score has been recorded (for example purely
    categorical feedback).
    """

    comments: Optional[List[str]] = None
    """
    `comments` is a sample of human-readable comments attached to feedback points
    for this key, in no particular order. May be empty; is not exhaustive when many
    comments exist.
    """

    contains_thread_feedback: Optional[bool] = None
    """
    `contains_thread_feedback` is true when at least one feedback point for this key
    was submitted at the thread level (rather than at an individual run). Always
    false on responses that already describe a single run in isolation.
    """

    errors: Optional[int] = None
    """
    `errors` is the number of feedback points recorded as errors rather than
    successful scores (for example an automated evaluator that raised an exception).
    Defaults to 0 when no errors occurred.
    """

    max: Optional[float] = None
    """
    `max` is the largest numeric feedback score recorded for this key on the run, or
    `null` when no numeric score has been recorded.
    """

    min: Optional[float] = None
    """
    `min` is the smallest numeric feedback score recorded for this key on the run,
    or `null` when no numeric score has been recorded.
    """

    n: Optional[int] = None
    """`n` is the number of feedback points recorded for this key on the run.

    For numeric feedback this is the sample size behind `avg`, `min`, `max`, and
    `stdev`; for categorical feedback it is the sum of the `values` counts.
    """

    sources: Optional[List[object]] = None
    """`sources` is a sample of feedback sources for this key.

    Each entry is either a plain string identifier (for example `"api"`, `"app"`,
    `"model"`) or a JSON object describing a synthetic source (for example
    `{"type": "__ls_composite_feedback"}` for a computed aggregate). Clients must
    tolerate both shapes.
    """

    stdev: Optional[float] = None
    """
    `stdev` is the sample standard deviation of numeric feedback scores for this key
    on the run, or `null` when it cannot be computed (for example fewer than two
    numeric scores, or purely categorical feedback).
    """

    values: Optional[Dict[str, int]] = None
    """
    `values` is the distribution of categorical feedback labels for this key,
    mapping each label to its occurrence count. Empty (`{}`) for purely numeric
    feedback.
    """


class PromptCostDetails(BaseModel):
    """
    `prompt_cost_details` is the per-sub-category sum of prompt cost details across the thread. Populated when `PROMPT_COST_DETAILS` is selected.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class PromptTokenDetails(BaseModel):
    """
    `prompt_token_details` is the per-sub-category sum of prompt token details across the thread. Populated when `PROMPT_TOKEN_DETAILS` is selected.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its prompt-token count."""


class ThreadStats(BaseModel):
    completion_cost: Optional[float] = None
    """
    `completion_cost` is the sum of per-trace completion costs across the thread, in
    USD. Populated when `COMPLETION_COST` is selected.
    """

    completion_cost_details: Optional[CompletionCostDetails] = None
    """
    `completion_cost_details` is the per-sub-category sum of completion cost details
    across the thread. Populated when `COMPLETION_COST_DETAILS` is selected.
    """

    completion_token_details: Optional[CompletionTokenDetails] = None
    """
    `completion_token_details` is the per-sub-category sum of completion token
    details across the thread. Populated when `COMPLETION_TOKEN_DETAILS` is
    selected.
    """

    completion_tokens: Optional[int] = None
    """
    `completion_tokens` is the sum of per-trace completion token counts across the
    thread. Populated when `COMPLETION_TOKENS` is selected.
    """

    feedback_stats: Optional[Dict[str, FeedbackStats]] = None
    """
    `feedback_stats` aggregates run-level feedback across the thread's traces, keyed
    by feedback key. Populated when `FEEDBACK_STATS` is selected.
    """

    first_start_time: Optional[datetime] = None
    """`first_start_time` is the earliest trace start time in the thread (RFC3339).

    Populated when `FIRST_START_TIME` is selected.
    """

    last_end_time: Optional[datetime] = None
    """`last_end_time` is the latest trace end time in the thread (RFC3339).

    Populated when `LAST_END_TIME` is selected.
    """

    last_start_time: Optional[datetime] = None
    """`last_start_time` is the latest trace start time in the thread (RFC3339).

    Populated when `LAST_START_TIME` is selected.
    """

    latency_p50_seconds: Optional[float] = None
    """
    `latency_p50_seconds` is the approximate p50 of trace latency across the thread,
    in seconds. Populated when `LATENCY_P50` is selected.
    """

    latency_p99_seconds: Optional[float] = None
    """
    `latency_p99_seconds` is the approximate p99 of trace latency across the thread,
    in seconds. Populated when `LATENCY_P99` is selected.
    """

    prompt_cost: Optional[float] = None
    """`prompt_cost` is the sum of per-trace prompt costs across the thread, in USD.

    Populated when `PROMPT_COST` is selected.
    """

    prompt_cost_details: Optional[PromptCostDetails] = None
    """
    `prompt_cost_details` is the per-sub-category sum of prompt cost details across
    the thread. Populated when `PROMPT_COST_DETAILS` is selected.
    """

    prompt_token_details: Optional[PromptTokenDetails] = None
    """
    `prompt_token_details` is the per-sub-category sum of prompt token details
    across the thread. Populated when `PROMPT_TOKEN_DETAILS` is selected.
    """

    prompt_tokens: Optional[int] = None
    """`prompt_tokens` is the sum of per-trace prompt token counts across the thread.

    Populated when `PROMPT_TOKENS` is selected.
    """

    total_cost: Optional[float] = None
    """`total_cost` is the sum of per-trace total costs across the thread, in USD.

    Populated when `TOTAL_COST` is selected.
    """

    total_tokens: Optional[int] = None
    """`total_tokens` is the sum of per-trace total token counts across the thread.

    Populated when `TOTAL_TOKENS` is selected.
    """

    turns: Optional[int] = None
    """`turns` is the number of distinct traces (turns) in the thread.

    Populated when `TURNS` is selected.
    """
