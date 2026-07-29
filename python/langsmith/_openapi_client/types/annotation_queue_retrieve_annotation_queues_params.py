# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["AnnotationQueueRetrieveAnnotationQueuesParams"]


class AnnotationQueueRetrieveAnnotationQueuesParams(TypedDict, total=False):
    assigned_to_me: bool

    dataset_id: Optional[str]

    ids: Optional[SequenceNotStr[str]]

    limit: int

    name: Optional[str]

    name_contains: Optional[str]

    offset: int

    queue_type: Optional[Literal["single", "pairwise"]]

    sort_by: Optional[str]

    sort_by_desc: bool

    tag_value_id: Optional[SequenceNotStr[str]]
