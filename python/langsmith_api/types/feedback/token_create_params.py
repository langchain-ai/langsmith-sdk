# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from ..._utils import PropertyInfo
from ..timedelta_input_param import TimedeltaInputParam
from .feedback_ingest_token_create_schema_param import FeedbackIngestTokenCreateSchemaParam

__all__ = [
    "TokenCreateParams",
    "FeedbackIngestTokenCreateSchema",
    "FeedbackIngestTokenCreateSchemaFeedbackConfig",
    "FeedbackIngestTokenCreateSchemaFeedbackConfigCategory",
    "Variant1",
]


class FeedbackIngestTokenCreateSchema(TypedDict, total=False):
    feedback_key: Required[str]

    run_id: Required[str]

    expires_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    expires_in: Optional[TimedeltaInputParam]
    """Timedelta input."""

    feedback_config: Optional[FeedbackIngestTokenCreateSchemaFeedbackConfig]


class FeedbackIngestTokenCreateSchemaFeedbackConfigCategory(TypedDict, total=False):
    """Specific value and label pair for feedback"""

    value: Required[float]

    label: Optional[str]


class FeedbackIngestTokenCreateSchemaFeedbackConfig(TypedDict, total=False):
    type: Required[Literal["continuous", "categorical", "freeform"]]
    """Enum for feedback types."""

    categories: Optional[Iterable[FeedbackIngestTokenCreateSchemaFeedbackConfigCategory]]

    max: Optional[float]

    min: Optional[float]


class Variant1(TypedDict, total=False):
    body: Required[Iterable[FeedbackIngestTokenCreateSchemaParam]]


TokenCreateParams: TypeAlias = Union[FeedbackIngestTokenCreateSchema, Variant1]
