# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import Required, TypeAlias, TypedDict

from .missing_param import MissingParam

__all__ = ["AnnotationQueueRubricItemSchemaParam", "RegexValidator"]

RegexValidator: TypeAlias = Union[str, MissingParam]


class AnnotationQueueRubricItemSchemaParam(TypedDict, total=False):
    feedback_key: Required[str]

    description: Optional[str]

    is_assertion: Optional[bool]

    is_required: Optional[bool]

    regex_validator: Optional[RegexValidator]

    score_descriptions: Optional[Dict[str, str]]

    value_descriptions: Optional[Dict[str, str]]
