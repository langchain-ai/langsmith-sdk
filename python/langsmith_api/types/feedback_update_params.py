# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["FeedbackUpdateParams", "FeedbackConfig", "FeedbackConfigCategory"]


class FeedbackUpdateParams(TypedDict, total=False):
    comment: Optional[str]

    correction: Union[Dict[str, object], str, None]

    feedback_config: Optional[FeedbackConfig]

    score: Union[float, bool, None]

    value: Union[float, bool, str, Dict[str, object], None]


class FeedbackConfigCategory(TypedDict, total=False):
    """Specific value and label pair for feedback"""

    value: Required[float]

    label: Optional[str]


class FeedbackConfig(TypedDict, total=False):
    type: Required[Literal["continuous", "categorical", "freeform"]]
    """Enum for feedback types."""

    categories: Optional[Iterable[FeedbackConfigCategory]]

    max: Optional[float]

    min: Optional[float]
