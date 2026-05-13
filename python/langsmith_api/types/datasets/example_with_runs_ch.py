# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel
from ..run_type_enum import RunTypeEnum
from ..feedback_schema import FeedbackSchema

__all__ = ["ExampleWithRunsCh", "Run"]


class Run(BaseModel):
    """Run schema for comparison view."""

    id: str

    name: str

    run_type: RunTypeEnum
    """Enum for run types."""

    session_id: str

    status: str

    trace_id: str

    app_path: Optional[str] = None

    completion_cost: Optional[str] = None

    completion_tokens: Optional[int] = None

    dotted_order: Optional[str] = None

    end_time: Optional[datetime] = None

    error: Optional[str] = None

    events: Optional[List[Dict[str, object]]] = None

    execution_order: Optional[int] = None

    extra: Optional[Dict[str, object]] = None

    feedback_stats: Optional[Dict[str, Dict[str, object]]] = None

    feedbacks: Optional[List[FeedbackSchema]] = None

    inputs: Optional[Dict[str, object]] = None

    inputs_preview: Optional[str] = None

    inputs_s3_urls: Optional[Dict[str, object]] = None

    manifest_id: Optional[str] = None

    manifest_s3_id: Optional[str] = None

    outputs: Optional[Dict[str, object]] = None

    outputs_preview: Optional[str] = None

    outputs_s3_urls: Optional[Dict[str, object]] = None

    parent_run_id: Optional[str] = None

    prompt_cost: Optional[str] = None

    prompt_tokens: Optional[int] = None

    reference_example_id: Optional[str] = None

    s3_urls: Optional[Dict[str, object]] = None

    serialized: Optional[Dict[str, object]] = None

    start_time: Optional[datetime] = None

    tags: Optional[List[str]] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None

    trace_max_start_time: Optional[datetime] = None

    trace_min_start_time: Optional[datetime] = None


class ExampleWithRunsCh(BaseModel):
    """Example schema with list of runs from ClickHouse.

    For non-grouped endpoint (/datasets/{dataset_id}/runs): runs from single session.
    For grouped endpoint (/datasets/{dataset_id}/group/runs): flat array of runs from
    all sessions, where each run has a session_id field for frontend to determine column placement.
    """

    id: str

    dataset_id: str

    inputs: Dict[str, object]

    name: str

    runs: List[Run]

    attachment_urls: Optional[Dict[str, object]] = None

    created_at: Optional[datetime] = None

    metadata: Optional[Dict[str, object]] = None

    modified_at: Optional[datetime] = None

    outputs: Optional[Dict[str, object]] = None

    source_run_id: Optional[str] = None
