# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["AnnotationQueuePopulateParams"]


class AnnotationQueuePopulateParams(TypedDict, total=False):
    queue_id: Required[str]

    session_ids: Required[SequenceNotStr[str]]
