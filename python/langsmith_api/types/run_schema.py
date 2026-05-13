# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .run_type_enum import RunTypeEnum

__all__ = ["RunSchema"]


class RunSchema(BaseModel):
    """Run schema."""

    id: str

    app_path: str

    dotted_order: str

    name: str

    run_type: RunTypeEnum
    """Enum for run types."""

    session_id: str

    status: str

    trace_id: str

    child_run_ids: Optional[List[str]] = None

    completion_cost: Optional[str] = None

    completion_cost_details: Optional[Dict[str, str]] = None

    completion_token_details: Optional[Dict[str, int]] = None

    completion_tokens: Optional[int] = None

    direct_child_run_ids: Optional[List[str]] = None

    end_time: Optional[datetime] = None

    error: Optional[str] = None

    events: Optional[List[Dict[str, object]]] = None

    execution_order: Optional[int] = None

    extra: Optional[Dict[str, object]] = None

    feedback_stats: Optional[Dict[str, Dict[str, object]]] = None

    first_token_time: Optional[datetime] = None

    in_dataset: Optional[bool] = None

    inputs: Optional[Dict[str, object]] = None

    inputs_preview: Optional[str] = None

    inputs_s3_urls: Optional[Dict[str, object]] = None

    last_queued_at: Optional[datetime] = None

    manifest_id: Optional[str] = None

    manifest_s3_id: Optional[str] = None

    messages: Optional[List[Dict[str, object]]] = None

    outputs: Optional[Dict[str, object]] = None

    outputs_preview: Optional[str] = None

    outputs_s3_urls: Optional[Dict[str, object]] = None

    parent_run_id: Optional[str] = None

    parent_run_ids: Optional[List[str]] = None

    price_model_id: Optional[str] = None

    prompt_cost: Optional[str] = None

    prompt_cost_details: Optional[Dict[str, str]] = None

    prompt_token_details: Optional[Dict[str, int]] = None

    prompt_tokens: Optional[int] = None

    reference_dataset_id: Optional[str] = None

    reference_example_id: Optional[str] = None

    s3_urls: Optional[Dict[str, object]] = None

    serialized: Optional[Dict[str, object]] = None

    share_token: Optional[str] = None

    start_time: Optional[datetime] = None

    tags: Optional[List[str]] = None

    thread_id: Optional[str] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None

    trace_first_received_at: Optional[datetime] = None

    trace_max_start_time: Optional[datetime] = None

    trace_min_start_time: Optional[datetime] = None

    trace_tier: Optional[Literal["longlived", "shortlived"]] = None

    trace_upgrade: Optional[bool] = None

    ttl_seconds: Optional[int] = None
