# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from .._utils import PropertyInfo
from .missing_param import MissingParam

__all__ = [
    "AnnotationQueueRubricItemSchemaParam",
    "FeedbackConfig",
    "FeedbackConfigFeedbackConfig",
    "FeedbackConfigFeedbackConfigCategory",
    "RegexValidator",
]


class FeedbackConfigFeedbackConfigCategory(TypedDict, total=False):
    """Specific value and label pair for feedback"""

    value: Required[float]

    label: Optional[str]


class FeedbackConfigFeedbackConfig(TypedDict, total=False):
    type: Required[Literal["continuous", "categorical", "freeform"]]
    """Enum for feedback types."""

    categories: Optional[Iterable[FeedbackConfigFeedbackConfigCategory]]

    max: Optional[float]

    min: Optional[float]


class FeedbackConfig(TypedDict, total=False):
    id: Required[str]

    feedback_config: Required[FeedbackConfigFeedbackConfig]

    feedback_key: Required[str]

    modified_at: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]

    tenant_id: Required[str]

    is_lower_score_better: Optional[bool]


RegexValidator: TypeAlias = Union[str, MissingParam]


class AnnotationQueueRubricItemSchemaParam(TypedDict, total=False):
    feedback_key: Required[str]

    description: Optional[str]

    feedback_config: Optional[FeedbackConfig]

    feedback_config_id: Optional[str]

    is_assertion: Optional[bool]

    is_required: Optional[bool]

    regex_validator: Optional[RegexValidator]

    score_descriptions: Optional[Dict[str, str]]

    value_descriptions: Optional[Dict[str, str]]
