# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ItemListResponse"]


class ItemListResponse(BaseModel):
    id: Optional[str] = None

    added_at: Optional[str] = None

    completed_by: Optional[List[str]] = None

    effective_added_at: Optional[str] = None

    item_type: Optional[Literal["RUN", "THREAD"]] = None

    last_reviewed_time: Optional[str] = None
    """LastReviewedTime is always present on the wire (null until reviewed)."""

    project_id: Optional[str] = None

    queue_id: Optional[str] = None

    reserved_by: Optional[List[str]] = None

    run_id: Optional[str] = None

    source_proposed_example_id: Optional[str] = None

    start_time: Optional[str] = None

    thread_id: Optional[str] = None
