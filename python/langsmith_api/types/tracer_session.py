# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["TracerSession"]


class TracerSession(BaseModel):
    """TracerSession schema."""

    id: str

    tenant_id: str

    completion_cost: Optional[str] = None

    completion_tokens: Optional[int] = None

    default_dataset_id: Optional[str] = None

    description: Optional[str] = None

    end_time: Optional[datetime] = None

    error_rate: Optional[float] = None

    extra: Optional[Dict[str, object]] = None

    feedback_stats: Optional[Dict[str, object]] = None

    first_token_p50: Optional[float] = None

    first_token_p99: Optional[float] = None

    last_run_start_time: Optional[datetime] = None

    last_run_start_time_live: Optional[datetime] = None

    latency_p50: Optional[float] = None

    latency_p99: Optional[float] = None

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
