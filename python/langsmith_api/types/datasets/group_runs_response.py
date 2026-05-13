# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel
from .example_with_runs_ch import ExampleWithRunsCh

__all__ = ["GroupRunsResponse", "Group", "GroupSession"]


class GroupSession(BaseModel):
    """TracerSession stats filtered to runs matching a specific metadata value.

    Extends TracerSession with:
    - example_count: unique examples (vs run_count = total runs including duplicates)
    - filter: ClickHouse filter for fetching runs in this session/group
    - min/max_start_time: time range for runs in this session/group
    """

    id: str

    filter: str

    tenant_id: str

    completion_cost: Optional[str] = None

    completion_tokens: Optional[int] = None

    default_dataset_id: Optional[str] = None

    description: Optional[str] = None

    end_time: Optional[datetime] = None

    error_rate: Optional[float] = None

    example_count: Optional[int] = None

    extra: Optional[Dict[str, object]] = None

    feedback_stats: Optional[Dict[str, object]] = None

    first_token_p50: Optional[float] = None

    first_token_p99: Optional[float] = None

    last_run_start_time: Optional[datetime] = None

    last_run_start_time_live: Optional[datetime] = None

    latency_p50: Optional[float] = None

    latency_p99: Optional[float] = None

    max_start_time: Optional[datetime] = None

    min_start_time: Optional[datetime] = None

    name: Optional[str] = None

    prompt_cost: Optional[str] = None

    prompt_tokens: Optional[int] = None

    reference_dataset_id: Optional[str] = None

    run_count: Optional[int] = None

    run_facets: Optional[List[Dict[str, object]]] = None

    session_feedback_stats: Optional[Dict[str, object]] = None

    start_time: Optional[datetime] = None

    streaming_rate: Optional[float] = None

    test_run_number: Optional[int] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None

    trace_tier: Optional[Literal["longlived", "shortlived"]] = None


class Group(BaseModel):
    """Group of examples with a specific metadata value across multiple sessions.

    Extends RunGroupBase with:
    - group_key: metadata value that defines this group
    - sessions: per-session stats for runs matching this metadata value
    - examples: shared examples across all sessions (intersection logic)
                with flat array of runs (each run has session_id field for frontend to determine column)
    - example_count: unique example count (pagination-aware, same across all sessions due to intersection)

    Inherited from RunGroupBase:
    - filter: metadata filter for this group (e.g., "and(eq(is_root, true), and(eq(metadata_key, 'model'), eq(metadata_value, 'gpt-4')))")
    - count: total run count across all sessions (includes duplicate runs)
    - total_tokens, total_cost: aggregate across sessions
    - min_start_time, max_start_time: time range across sessions
    - latency_p50, latency_p99: aggregate latency stats across sessions
    - feedback_stats: weighted average feedback across sessions

    Additional aggregate stats:
    - prompt_tokens, completion_tokens: separate token counts
    - prompt_cost, completion_cost: separate costs
    - error_rate: average error rate
    """

    example_count: int

    examples: List[ExampleWithRunsCh]

    filter: str

    group_key: Union[str, float]

    sessions: List[GroupSession]

    completion_cost: Optional[str] = None

    completion_tokens: Optional[int] = None

    count: Optional[int] = None

    error_rate: Optional[float] = None

    feedback_stats: Optional[Dict[str, object]] = None

    latency_p50: Optional[float] = None

    latency_p99: Optional[float] = None

    max_start_time: Optional[datetime] = None

    min_start_time: Optional[datetime] = None

    prompt_cost: Optional[str] = None

    prompt_tokens: Optional[int] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None


class GroupRunsResponse(BaseModel):
    """Response for grouped comparison view of dataset examples.

    Returns dataset examples grouped by a run metadata value (e.g., model='gpt-4').
    Optional filters are applied to all runs before grouping.

    Shows:
    - Which examples were executed with each metadata value
    - Per-session aggregate statistics for runs on those examples
    - The actual example data with their associated runs

    Used for comparing how different sessions performed on the same set of examples.
    """

    groups: List[Group]
