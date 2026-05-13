# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .annotation_queue_rubric_item_schema import AnnotationQueueRubricItemSchema

__all__ = ["AnnotationQueueRetrieveResponse", "AssignedReviewer"]


class AssignedReviewer(BaseModel):
    """Identity info for an assigned reviewer on an annotation queue."""

    id: str

    email: Optional[str] = None

    name: Optional[str] = None


class AnnotationQueueRetrieveResponse(BaseModel):
    """AnnotationQueue schema with rubric."""

    id: str

    name: str

    queue_type: Literal["single", "pairwise"]

    tenant_id: str

    assigned_reviewers: Optional[List[AssignedReviewer]] = None

    created_at: Optional[datetime] = None

    default_dataset: Optional[str] = None

    description: Optional[str] = None

    enable_reservations: Optional[bool] = None

    metadata: Optional[Dict[str, object]] = None

    num_reviewers_per_item: Optional[int] = None

    reservation_minutes: Optional[int] = None

    reviewer_access_mode: Optional[str] = None

    rubric_instructions: Optional[str] = None

    rubric_items: Optional[List[AnnotationQueueRubricItemSchema]] = None

    run_rule_id: Optional[str] = None

    source_rule_id: Optional[str] = None

    updated_at: Optional[datetime] = None
