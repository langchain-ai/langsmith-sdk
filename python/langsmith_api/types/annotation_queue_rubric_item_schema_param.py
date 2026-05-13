# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

__all__ = ["AnnotationQueueRubricItemSchemaParam"]


class AnnotationQueueRubricItemSchemaParam(TypedDict, total=False):
    feedback_key: Required[str]

    description: Optional[str]

    is_assertion: Optional[bool]

    is_required: Optional[bool]

    score_descriptions: Optional[Dict[str, str]]

    value_descriptions: Optional[Dict[str, str]]
