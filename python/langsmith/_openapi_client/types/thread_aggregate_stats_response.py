# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["ThreadAggregateStatsResponse", "ThreadFeedbackStats"]


class ThreadFeedbackStats(BaseModel):
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


class ThreadAggregateStatsResponse(BaseModel):
    completion_cost: Optional[float] = None
    """`completion_cost` is the completion cost across matching traces in USD."""

    completion_cost_details: Optional[Dict[str, float]] = None
    """`completion_cost_details` contains completion-cost totals by category."""

    completion_token_details: Optional[Dict[str, int]] = None
    """`completion_token_details` contains completion-token totals by category."""

    completion_tokens: Optional[int] = None
    """`completion_tokens` is the sum of completion tokens across matching traces."""

    error_rate: Optional[float] = None
    """`error_rate` is the fraction of matching traces that contain an error."""

    first_token_p50_seconds: Optional[float] = None
    """
    `first_token_p50_seconds` is the approximate median time to first token in
    seconds. Populated when `FIRST_TOKEN_P50` is selected.
    """

    first_token_p99_seconds: Optional[float] = None
    """`first_token_p99_seconds` is the approximate p99 time to first token in seconds.

    Populated when `FIRST_TOKEN_P99` is selected.
    """

    latency_p50_seconds: Optional[float] = None
    """`latency_p50_seconds` is the approximate median trace latency in seconds.

    Populated when `LATENCY_P50` is selected.
    """

    latency_p99_seconds: Optional[float] = None
    """`latency_p99_seconds` is the approximate p99 trace latency in seconds.

    Populated when `LATENCY_P99` is selected.
    """

    median_tokens: Optional[int] = None
    """`median_tokens` is the approximate median of total tokens across matching
    traces.

    Populated when `MEDIAN_TOKENS` is selected.
    """

    prompt_cost: Optional[float] = None
    """`prompt_cost` is the prompt cost across matching traces in USD."""

    prompt_cost_details: Optional[Dict[str, float]] = None
    """`prompt_cost_details` contains prompt-cost totals by category."""

    prompt_token_details: Optional[Dict[str, int]] = None
    """`prompt_token_details` contains prompt-token totals by category."""

    prompt_tokens: Optional[int] = None
    """`prompt_tokens` is the sum of prompt tokens across matching traces."""

    streaming_rate: Optional[float] = None
    """
    `streaming_rate` is the fraction of completed matching traces that streamed
    tokens.
    """

    thread_count: Optional[int] = None
    """`thread_count` is the number of distinct threads matching the query.

    Populated when `THREAD_COUNT` is selected.
    """

    thread_feedback_stats: Optional[Dict[str, ThreadFeedbackStats]] = None
    """
    `thread_feedback_stats` contains aggregate thread-level feedback statistics
    keyed by feedback key. Populated when `THREAD_FEEDBACK_STATS` is selected.
    """

    total_cost: Optional[float] = None
    """`total_cost` is the total cost across matching traces in USD."""

    total_tokens: Optional[int] = None
    """`total_tokens` is the sum of all tokens across matching traces."""

    trace_count: Optional[int] = None
    """`trace_count` is the number of traces in the matching threads.

    Populated when `TRACE_COUNT` is selected.
    """
