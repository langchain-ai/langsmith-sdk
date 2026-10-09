# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal, TypeAlias

from .missing import Missing
from .._models import BaseModel

__all__ = [
    "AnnotationQueueRubricItemSchema",
    "FeedbackConfig",
    "FeedbackConfigFeedbackConfig",
    "FeedbackConfigFeedbackConfigCategory",
    "RegexValidator",
]


class FeedbackConfigFeedbackConfigCategory(BaseModel):
    """Specific value and label pair for feedback"""

    value: float

    label: Optional[str] = None


class FeedbackConfigFeedbackConfig(BaseModel):
    type: Literal["continuous", "categorical", "freeform"]
    """Enum for feedback types."""

    categories: Optional[List[FeedbackConfigFeedbackConfigCategory]] = None

    max: Optional[float] = None

    min: Optional[float] = None


class FeedbackConfig(BaseModel):
    id: str

    feedback_config: FeedbackConfigFeedbackConfig

    feedback_key: str

    modified_at: datetime

    tenant_id: str

    is_lower_score_better: Optional[bool] = None


RegexValidator: TypeAlias = Union[str, Missing, None]


class AnnotationQueueRubricItemSchema(BaseModel):
    feedback_key: str

    description: Optional[str] = None

    feedback_config: Optional[FeedbackConfig] = None

    feedback_config_id: Optional[str] = None

    is_assertion: Optional[bool] = None

    is_required: Optional[bool] = None

    regex_validator: Optional[RegexValidator] = None

    score_descriptions: Optional[Dict[str, str]] = None

    value_descriptions: Optional[Dict[str, str]] = None
