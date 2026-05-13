# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, TypedDict

__all__ = ["AnnotationQueueRetrieveSizeParams"]


class AnnotationQueueRetrieveSizeParams(TypedDict, total=False):
    status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]]
