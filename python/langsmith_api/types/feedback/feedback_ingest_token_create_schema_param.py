# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from ..._utils import PropertyInfo
from ..timedelta_input_param import TimedeltaInputParam

__all__ = ["FeedbackIngestTokenCreateSchemaParam", "FeedbackConfig", "FeedbackConfigCategory"]


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


class FeedbackIngestTokenCreateSchemaParam(TypedDict, total=False):
    """Feedback ingest token create schema."""

    feedback_key: Required[str]

    run_id: Required[str]

    expires_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    expires_in: Optional[TimedeltaInputParam]
    """Timedelta input."""

    feedback_config: Optional[FeedbackConfig]
