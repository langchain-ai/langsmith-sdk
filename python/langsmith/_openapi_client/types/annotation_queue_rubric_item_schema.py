# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional

from .._models import BaseModel

__all__ = ["AnnotationQueueRubricItemSchema"]


class AnnotationQueueRubricItemSchema(BaseModel):
    feedback_key: str

    description: Optional[str] = None

    is_assertion: Optional[bool] = None

    is_required: Optional[bool] = None

    score_descriptions: Optional[Dict[str, str]] = None

    value_descriptions: Optional[Dict[str, str]] = None
