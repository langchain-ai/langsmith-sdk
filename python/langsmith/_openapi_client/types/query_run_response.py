# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = [
    "QueryRunResponse",
    "CompletionCostDetails",
    "CompletionTokenDetails",
    "Event",
    "FeedbackStats",
    "PromptCostDetails",
    "PromptTokenDetails",
]


class CompletionCostDetails(BaseModel):
    """`completion_cost_details` is the per-category USD breakdown of `completion_cost`.

    Categories mirror `completion_token_details`. Returned only when the `COMPLETION_COST_DETAILS` field is requested.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class CompletionTokenDetails(BaseModel):
    """`completion_token_details` is the per-category breakdown of `completion_tokens`.

    Category names are model-specific (for example `reasoning`, `audio`). Returned only when the `COMPLETION_TOKEN_DETAILS` field is requested.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its completion-token count."""


class Event(BaseModel):
    kwargs: Optional[object] = None
    """
    `kwargs` is the event payload — an opaque JSON object whose shape depends on
    `name` and on the emitting SDK. For example LangChain emits `{"token": {...}}`
    for `new_token` events, tool-call start/end details for tool events, and
    arbitrary user-defined payloads for custom events. Clients should treat `kwargs`
    as untyped JSON: do not assume specific keys exist for a given `name`, and
    tolerate additional unknown keys appearing over time.
    """

    name: Optional[str] = None
    """`name` is the event kind.

    Common values emitted by the LangChain/LangSmith tracer SDKs include `"start"`,
    `"end"`, and `"new_token"`, but applications may emit arbitrary strings for
    their own instrumentation.
    """

    time: Optional[datetime] = None
    """
    `time` is when the event occurred (RFC3339 date-time with millisecond
    precision).
    """


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
    """`prompt_cost_details` is the per-category USD breakdown of `prompt_cost`.

    Categories mirror `prompt_token_details`. Returned only when the `PROMPT_COST_DETAILS` field is requested.
    """

    raw: Optional[Dict[str, float]] = None
    """`raw` maps each category name to its estimated USD cost."""


class PromptTokenDetails(BaseModel):
    """`prompt_token_details` is the per-category breakdown of `prompt_tokens`.

    Category names are model-specific (for example `cache_read`, `cache_write`). Returned only when the `PROMPT_TOKEN_DETAILS` field is requested.
    """

    raw: Optional[Dict[str, int]] = None
    """`raw` maps each category name to its prompt-token count."""


class QueryRunResponse(BaseModel):
    id: Optional[str] = None
    """`id` is this run's UUID."""

    app_path: Optional[str] = None
    """
    `app_path` identifies the application code location that produced this run, if
    recorded.
    """

    attachments: Optional[Dict[str, str]] = None
    """
    `attachments` maps each attachment file name to a pre-signed HTTPS download URL.
    """

    completion_cost: Optional[float] = None
    """`completion_cost` is estimated USD cost for the completion."""

    completion_cost_details: Optional[CompletionCostDetails] = None
    """`completion_cost_details` is the per-category USD breakdown of
    `completion_cost`.

    Categories mirror `completion_token_details`. Returned only when the
    `COMPLETION_COST_DETAILS` field is requested.
    """

    completion_token_details: Optional[CompletionTokenDetails] = None
    """`completion_token_details` is the per-category breakdown of `completion_tokens`.

    Category names are model-specific (for example `reasoning`, `audio`). Returned
    only when the `COMPLETION_TOKEN_DETAILS` field is requested.
    """

    completion_tokens: Optional[int] = None
    """`completion_tokens` is the completion-side token count."""

    dotted_order: Optional[str] = None
    """`dotted_order` is the hierarchical ordering key for trace trees."""

    end_time: Optional[datetime] = None
    """`end_time` is when the run ended (RFC3339 date-time).

    JSON null if the run has not finished yet.
    """

    error: Optional[str] = None
    """`error` is the error message when `status` indicates failure."""

    error_preview: Optional[str] = None
    """`error_preview` is a truncated plain-text error snippet."""

    events: Optional[List[Event]] = None
    """`events` is the ordered list of run events (for example streaming tokens)."""

    extra: Optional[object] = None
    """`extra` is additional runtime JSON attached to the run."""

    feedback_stats: Optional[Dict[str, FeedbackStats]] = None
    """`feedback_stats` aggregates feedback scores keyed by feedback key."""

    first_token_time: Optional[datetime] = None
    """
    `first_token_time` is when the first output token was produced (RFC3339
    date-time), when recorded for streamed runs.
    """

    inputs: Optional[object] = None
    """`inputs` is the run input payload (arbitrary JSON object)."""

    inputs_preview: Optional[str] = None
    """`inputs_preview` is a truncated plain-text preview of inputs."""

    is_in_dataset: Optional[bool] = None
    """`is_in_dataset` is true when this run is linked to a dataset example."""

    is_root: Optional[bool] = None
    """`is_root` is true when this run has no parent (it is the trace root)."""

    latency_seconds: Optional[float] = None
    """`latency_seconds` is wall-clock duration from start to end in seconds."""

    manifest: Optional[object] = None
    """
    `manifest` is the serialized configuration of the traced component (for example
    the model parameters, prompt template, or pipeline definition), when recorded.
    """

    metadata: Optional[object] = None
    """`metadata` is arbitrary user-defined JSON metadata."""

    name: Optional[str] = None
    """
    `name` is a human-readable label for the run (for example the model name,
    function name, or step name chosen when the run was traced).
    """

    outputs: Optional[object] = None
    """`outputs` is the run output payload (arbitrary JSON object)."""

    outputs_preview: Optional[str] = None
    """`outputs_preview` is a truncated plain-text preview of outputs."""

    parent_run_ids: Optional[List[str]] = None
    """
    `parent_run_ids` lists ancestor run UUIDs from the trace root down to the direct
    parent.
    """

    price_model_id: Optional[str] = None
    """
    `price_model_id` identifies the pricing model UUID used for cost estimates, when
    recorded.
    """

    project_id: Optional[str] = None
    """`project_id` is the tracing project UUID this run was logged to."""

    prompt_cost: Optional[float] = None
    """`prompt_cost` is estimated USD cost for the prompt."""

    prompt_cost_details: Optional[PromptCostDetails] = None
    """`prompt_cost_details` is the per-category USD breakdown of `prompt_cost`.

    Categories mirror `prompt_token_details`. Returned only when the
    `PROMPT_COST_DETAILS` field is requested.
    """

    prompt_token_details: Optional[PromptTokenDetails] = None
    """`prompt_token_details` is the per-category breakdown of `prompt_tokens`.

    Category names are model-specific (for example `cache_read`, `cache_write`).
    Returned only when the `PROMPT_TOKEN_DETAILS` field is requested.
    """

    prompt_tokens: Optional[int] = None
    """`prompt_tokens` is the prompt-side token count."""

    reference_dataset_id: Optional[str] = None
    """`reference_dataset_id` is the dataset UUID for the reference example, if any."""

    reference_example_id: Optional[str] = None
    """
    `reference_example_id` is the dataset example UUID this run was compared
    against, if any.
    """

    run_type: Optional[Literal["TOOL", "CHAIN", "LLM", "RETRIEVER", "EMBEDDING", "PROMPT", "PARSER"]] = None
    """
    `run_type` identifies what kind of operation this run represents (for example an
    LLM call, a tool invocation, or a chain step). See the `RunType` enum for
    allowed values.
    """

    share_url: Optional[str] = None
    """
    `share_url` is the fully-qualified URL of this run's public view, rooted at the
    deployment's LangSmith app origin (for example
    `https://smith.langchain.com/public/4f7a1b2c-8d9e-4a0b-9c1d-2e3f4a5b6c7d/r`). It
    is returned only when `SHARE_URL` is included in `selects`, and only when the
    run has been explicitly shared; the URL remains stable until the run is
    unshared. Anyone with this URL can view the run anonymously, so treat it as a
    secret and do not log it.
    """

    start_time: Optional[datetime] = None
    """`start_time` is when the run started (RFC3339 date-time)."""

    status: Optional[Literal["SUCCESS", "ERROR", "PENDING"]] = None
    """`status` is the completion status of the run."""

    tags: Optional[List[str]] = None
    """`tags` lists user-defined tags on this run."""

    thread_evaluation_time: Optional[datetime] = None
    """
    `thread_evaluation_time` is thread-level evaluation timing (RFC3339 date-time),
    when recorded.
    """

    thread_id: Optional[str] = None
    """`thread_id` is the conversation thread UUID this run belongs to, if any."""

    total_cost: Optional[float] = None
    """`total_cost` is total estimated USD cost (prompt plus completion)."""

    total_tokens: Optional[int] = None
    """`total_tokens` is prompt plus completion tokens."""

    trace_id: Optional[str] = None
    """`trace_id` is the root trace UUID; for a root run it matches `id`."""
