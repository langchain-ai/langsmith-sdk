# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import Literal, TypeAlias, TypedDict

from .missing_param import MissingParam
from .annotation_queue_rubric_item_schema_param import AnnotationQueueRubricItemSchemaParam

__all__ = ["AnnotationQueueUpdateParams", "EnableReservations", "Metadata", "NumReviewersPerItem", "ReservationMinutes"]


class AnnotationQueueUpdateParams(TypedDict, total=False):
    default_dataset: Optional[str]

    description: Optional[str]

    enable_reservations: EnableReservations

    metadata: Optional[Metadata]

    name: Optional[str]

    num_reviewers_per_item: Optional[NumReviewersPerItem]

    reservation_minutes: Optional[ReservationMinutes]

    reviewer_access_mode: Optional[Literal["any", "assigned"]]

    rubric_instructions: Optional[str]

    rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]]


EnableReservations: TypeAlias = Union[bool, MissingParam]

Metadata: TypeAlias = Union[Dict[str, object], MissingParam]

NumReviewersPerItem: TypeAlias = Union[int, MissingParam]

ReservationMinutes: TypeAlias = Union[int, MissingParam]
