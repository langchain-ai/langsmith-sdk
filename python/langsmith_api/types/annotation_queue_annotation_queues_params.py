# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .annotation_queue_rubric_item_schema_param import AnnotationQueueRubricItemSchemaParam

__all__ = ["AnnotationQueueAnnotationQueuesParams"]


class AnnotationQueueAnnotationQueuesParams(TypedDict, total=False):
    name: Required[str]

    id: str

    created_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    default_dataset: Optional[str]

    description: Optional[str]

    enable_reservations: Optional[bool]

    metadata: Optional[Dict[str, object]]

    num_reviewers_per_item: Optional[int]

    reservation_minutes: Optional[int]

    reviewer_access_mode: str

    rubric_instructions: Optional[str]

    rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]]

    session_ids: Optional[SequenceNotStr[str]]

    updated_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]
