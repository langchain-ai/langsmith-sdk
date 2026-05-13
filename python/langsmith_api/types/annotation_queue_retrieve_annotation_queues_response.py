# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["AnnotationQueueRetrieveAnnotationQueuesResponse", "AssignedReviewer"]


class AssignedReviewer(BaseModel):
    """Identity info for an assigned reviewer on an annotation queue."""

    id: str

    email: Optional[str] = None

    name: Optional[str] = None


class AnnotationQueueRetrieveAnnotationQueuesResponse(BaseModel):
    """AnnotationQueue schema with size."""

    id: str

    name: str

    queue_type: Literal["single", "pairwise"]

    tenant_id: str

    total_runs: int

    assigned_reviewers: Optional[List[AssignedReviewer]] = None

    created_at: Optional[datetime] = None

    default_dataset: Optional[str] = None

    description: Optional[str] = None

    enable_reservations: Optional[bool] = None

    metadata: Optional[Dict[str, object]] = None

    num_reviewers_per_item: Optional[int] = None

    reservation_minutes: Optional[int] = None

    reviewer_access_mode: Optional[str] = None

    run_rule_id: Optional[str] = None

    source_rule_id: Optional[str] = None

    updated_at: Optional[datetime] = None
