# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Union, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["FeedbackSchema", "FeedbackSource"]


class FeedbackSource(BaseModel):
    """The feedback source loaded from the database."""

    ls_user_id: Optional[str] = None

    metadata: Optional[Dict[str, object]] = None

    type: Optional[str] = None

    user_id: Optional[str] = None

    user_name: Optional[str] = None


class FeedbackSchema(BaseModel):
    """Schema for getting feedback."""

    id: str

    key: str

    comment: Optional[str] = None

    comparative_experiment_id: Optional[str] = None

    correction: Union[Dict[str, object], str, None] = None

    created_at: Optional[datetime] = None

    extra: Optional[Dict[str, object]] = None

    feedback_group_id: Optional[str] = None

    feedback_source: Optional[FeedbackSource] = None
    """The feedback source loaded from the database."""

    feedback_thread_id: Optional[str] = None

    is_root: Optional[bool] = None

    modified_at: Optional[datetime] = None

    run_id: Optional[str] = None

    score: Union[float, bool, None] = None

    session_id: Optional[str] = None

    start_time: Optional[datetime] = None

    trace_id: Optional[str] = None

    value: Union[float, bool, str, Dict[str, object], None] = None
