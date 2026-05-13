# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["ThreadListItem", "FeedbackStats"]


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


class ThreadListItem(BaseModel):
    count: Optional[int] = None
    """
    `count` is how many root traces (conversation turns) fall in this thread for the
    query time range.
    """

    feedback_stats: Optional[Dict[str, FeedbackStats]] = None
    """
    `feedback_stats` is the aggregated feedback across traces in the thread, keyed
    by feedback key; shape matches `feedback_stats` on a single run.
    """

    first_inputs: Optional[str] = None
    """
    `first_inputs` is a truncated preview of inputs from the earliest trace in the
    thread for the query window.
    """

    first_trace_id: Optional[str] = None
    """
    `first_trace_id` is the root trace UUID for the chronologically first trace in
    the query time window.
    """

    last_error: Optional[str] = None
    """
    `last_error` is a short error summary from the most recent failing trace in the
    thread. Absent when there is no error in the window.
    """

    last_outputs: Optional[str] = None
    """
    `last_outputs` is a truncated preview of outputs from the latest trace in the
    thread for the query window.
    """

    last_trace_id: Optional[str] = None
    """
    `last_trace_id` is the root trace UUID for the chronologically last trace in the
    query time window.
    """

    latency_p50: Optional[float] = None
    """
    `latency_p50` is the approximate median end-to-end latency of traces in the
    thread, in seconds.
    """

    latency_p99: Optional[float] = None
    """
    `latency_p99` is the approximate 99th percentile end-to-end latency of traces in
    the thread, in seconds.
    """

    max_start_time: Optional[datetime] = None
    """
    `max_start_time` is the latest trace start time in the thread (RFC3339
    date-time).
    """

    min_start_time: Optional[datetime] = None
    """
    `min_start_time` is the earliest trace start time in the thread (RFC3339
    date-time).
    """

    start_time: Optional[datetime] = None
    """
    `start_time` is a reference start time for this row (RFC3339 date-time), such as
    for sorting.
    """

    thread_id: Optional[str] = None
    """
    `thread_id` identifies this conversation thread within the project from the
    request body `project_id`.
    """

    total_cost: Optional[float] = None
    """`total_cost` is the sum of estimated USD cost across those traces."""

    total_cost_details: Optional[Dict[str, float]] = None
    """
    `total_cost_details` sums per-category estimated USD cost across traces in the
    thread. Keys mirror `total_token_details`.

    Example: `{"cache_read": 0.012, "reasoning": 0.008}`.
    """

    total_token_details: Optional[Dict[str, int]] = None
    """`total_token_details` sums per-category token counts across traces in the
    thread.

    Keys are model-specific category names (for example `cache_read`, `cache_write`,
    `reasoning`, `audio`).

    Example: `{"cache_read": 400, "reasoning": 120}`.
    """

    total_tokens: Optional[int] = None
    """`total_tokens` is the sum of token usage across those traces."""

    trace_id: Optional[str] = None
    """
    `trace_id` is a representative root trace UUID when the summary includes one,
    for example for deep links.
    """
