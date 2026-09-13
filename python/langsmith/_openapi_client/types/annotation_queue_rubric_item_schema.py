# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Union, Optional
from typing_extensions import TypeAlias

from .missing import Missing
from .._models import BaseModel

__all__ = ["AnnotationQueueRubricItemSchema", "RegexValidator"]

RegexValidator: TypeAlias = Union[str, Missing, None]


class AnnotationQueueRubricItemSchema(BaseModel):
    feedback_key: str

    description: Optional[str] = None

    is_assertion: Optional[bool] = None

    is_required: Optional[bool] = None

    regex_validator: Optional[RegexValidator] = None

    score_descriptions: Optional[Dict[str, str]] = None

    value_descriptions: Optional[Dict[str, str]] = None
