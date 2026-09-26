# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = [
    "Issue",
    "Evidence",
    "EvidenceSeries",
    "EvidenceSeriesMetricDefinition",
    "EvidenceSeriesMetricDefinitionDenominator",
    "EvidenceSeriesMetricDefinitionDenominatorParams",
    "EvidenceSeriesMetricDefinitionNumerator",
    "EvidenceSeriesMetricDefinitionNumeratorParams",
    "EvidenceSeriesMetricDefinitionParams",
    "FixVerification",
    "Fix",
    "LinearContext",
    "LinearSync",
    "ValidationResult",
]


class EvidenceSeriesMetricDefinitionDenominatorParams(BaseModel):
    """required when type=percentile"""

    bucket_count: Optional[int] = None

    feedback_key: Optional[str] = None

    p: Optional[float] = None


class EvidenceSeriesMetricDefinitionDenominator(BaseModel):
    type: Literal["count", "sum", "avg", "min", "max", "percentile", "ratio", "histogram"]
    """An operand is non-composite, so ratio is rejected here too."""

    entity: Optional[Literal["run", "feedback"]] = None
    """Entity selects what a type=count metric counts.

    Only valid when type=count; defaults to MetricEntityRun. entity=feedback
    requires params.feedback_key and counts individual feedback records rather than
    runs.
    """

    field: Optional[
        Literal[
            "latency_seconds",
            "first_token_seconds",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "total_cost",
            "prompt_cost",
            "completion_cost",
            "feedback_score",
        ]
    ] = None

    filter: Optional[str] = None

    params: Optional[EvidenceSeriesMetricDefinitionDenominatorParams] = None
    """required when type=percentile"""


class EvidenceSeriesMetricDefinitionNumeratorParams(BaseModel):
    """required when type=percentile"""

    bucket_count: Optional[int] = None

    feedback_key: Optional[str] = None

    p: Optional[float] = None


class EvidenceSeriesMetricDefinitionNumerator(BaseModel):
    """Numerator and Denominator are required when type=ratio."""

    type: Literal["count", "sum", "avg", "min", "max", "percentile", "ratio", "histogram"]
    """An operand is non-composite, so ratio is rejected here too."""

    entity: Optional[Literal["run", "feedback"]] = None
    """Entity selects what a type=count metric counts.

    Only valid when type=count; defaults to MetricEntityRun. entity=feedback
    requires params.feedback_key and counts individual feedback records rather than
    runs.
    """

    field: Optional[
        Literal[
            "latency_seconds",
            "first_token_seconds",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "total_cost",
            "prompt_cost",
            "completion_cost",
            "feedback_score",
        ]
    ] = None

    filter: Optional[str] = None

    params: Optional[EvidenceSeriesMetricDefinitionNumeratorParams] = None
    """required when type=percentile"""


class EvidenceSeriesMetricDefinitionParams(BaseModel):
    """percentile p or histogram bucket_count"""

    bucket_count: Optional[int] = None

    feedback_key: Optional[str] = None

    p: Optional[float] = None


class EvidenceSeriesMetricDefinition(BaseModel):
    type: Literal["count", "sum", "avg", "min", "max", "percentile", "ratio", "histogram"]
    """histogram is reserved and rejected; the tag publishes what is accepted."""

    denominator: Optional[EvidenceSeriesMetricDefinitionDenominator] = None

    entity: Optional[Literal["run", "feedback"]] = None
    """Entity selects what a type=count metric counts.

    Only valid when type=count; defaults to MetricEntityRun. entity=feedback
    requires params.feedback_key and counts individual feedback records rather than
    runs.
    """

    field: Optional[
        Literal[
            "latency_seconds",
            "first_token_seconds",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
            "total_cost",
            "prompt_cost",
            "completion_cost",
            "feedback_score",
        ]
    ] = None

    numerator: Optional[EvidenceSeriesMetricDefinitionNumerator] = None
    """Numerator and Denominator are required when type=ratio."""

    params: Optional[EvidenceSeriesMetricDefinitionParams] = None
    """percentile p or histogram bucket_count"""


class EvidenceSeries(BaseModel):
    metric_definition: EvidenceSeriesMetricDefinition

    run_filter: Optional[str] = None
    """Narrows what is measured; the renderer ANDs its root scope over it."""

    window_end: Optional[datetime] = None

    window_start: Optional[datetime] = None
    """The view the chart opens at, not a clamp. Start alone renders start -> now."""


class Evidence(BaseModel):
    """Nil for the trace-list issues that are the norm."""

    type: Literal["series"]

    series: Optional[EvidenceSeries] = None


class FixVerification(BaseModel):
    attempt: Optional[int] = None

    baseline_experiment_id: Optional[str] = None

    dataset_id: Optional[str] = None

    parent_deployment_id: Optional[str] = None

    preview_deployment_id: Optional[str] = None

    preview_experiment_id: Optional[str] = None

    reason: Optional[str] = None

    root_trace_ids: Optional[List[str]] = None

    status: Optional[
        Literal["awaiting_preview", "verifying", "passed", "failed", "inconclusive", "timeout", "error"]
    ] = None

    updated_at: Optional[datetime] = None


class Fix(BaseModel):
    id: str

    branch: Optional[str] = None

    created_at: datetime

    pr_number: Optional[int] = None

    repo_url: str

    updated_at: datetime


class LinearContext(BaseModel):
    github_pr_urls: Optional[List[str]] = None

    workflow_state: Optional[str] = None


class LinearSync(BaseModel):
    identifier: Optional[str] = None

    issue_id: Optional[str] = None

    last_attempted_at: Optional[datetime] = None

    last_error: Optional[str] = None

    last_synced_at: Optional[datetime] = None

    linear_issue_id: Optional[str] = None

    state: Optional[Literal["pending", "synced", "failed", "auth_required", "paused"]] = None

    url: Optional[str] = None


class ValidationResult(BaseModel):
    active_revision_id: Optional[str] = None

    baseline_experiment_id: Optional[str] = None

    completed_at: Optional[datetime] = None

    dataset_id: Optional[str] = None

    deployment_id: Optional[str] = None

    outcome: Optional[Literal["reproduced", "not_reproduced", "inconclusive", "error"]] = None

    reason: Optional[str] = None

    root_trace_ids: Optional[List[str]] = None


class Issue(BaseModel):
    id: Optional[str] = None

    actions: Optional[object] = None

    auto_resolution_evidence: Optional[object] = None

    auto_resolution_state: Optional[str] = None
    """Nil unless eligible: "auto_close" or "prompt".

    Evidence carries the deciding gate.
    """

    created_at: Optional[str] = None

    description: Optional[str] = None

    evidence: Optional[Evidence] = None
    """Nil for the trace-list issues that are the norm."""

    first_seen_at: Optional[str] = None

    fix_branch: Optional[str] = None
    """Legacy: branch of the oldest fix in the board's oldest connected repository."""

    fix_dispatched_at: Optional[str] = None

    fix_pr_number: Optional[int] = None

    fix_prompt: Optional[str] = None
    """
    Issue-level: the problem every fix shares, and the last time a fix run was
    dispatched for this issue — one run works several fixes.
    """

    fix_verification: Optional[FixVerification] = None

    fixes: Optional[List[Fix]] = None
    """Newest first."""

    last_seen_at: Optional[str] = None

    linear_context: Optional[LinearContext] = None

    linear_sync: Optional[LinearSync] = None

    name: Optional[str] = None

    proposed_context_fixes: Optional[List[object]] = None

    proposed_examples: Optional[List[object]] = None

    proposed_fix: Optional[str] = None

    proposed_prompt_fixes: Optional[List[object]] = None

    recurrences_since_watching: Optional[int] = None
    """
    RecurrencesSinceWatching counts linked traces whose run start_time is after
    watching_since — i.e. recurrences observed during the current watch period.
    """

    session_id: Optional[str] = None

    severity: Optional[Literal[0, 1, 2, 3]] = None

    status: Optional[Literal["open", "fixing", "watching", "completed", "ignored"]] = None

    tags: Optional[List[str]] = None

    tenant_id: Optional[str] = None

    traces: Optional[object] = None

    updated_at: Optional[str] = None

    validation_result: Optional[ValidationResult] = None

    watching_since: Optional[str] = None
