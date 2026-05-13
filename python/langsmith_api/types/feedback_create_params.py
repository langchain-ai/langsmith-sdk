# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from .._utils import PropertyInfo
from .api_feedback_source_param import APIFeedbackSourceParam
from .app_feedback_source_param import AppFeedbackSourceParam
from .model_feedback_source_param import ModelFeedbackSourceParam
from .auto_eval_feedback_source_param import AutoEvalFeedbackSourceParam

__all__ = ["FeedbackCreateParams", "FeedbackConfig", "FeedbackConfigCategory", "FeedbackSource"]


class FeedbackCreateParams(TypedDict, total=False):
    key: Required[str]

    id: str

    comment: Optional[str]

    comparative_experiment_id: Optional[str]

    correction: Union[Dict[str, object], str, None]

    created_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    error: Optional[bool]

    feedback_config: Optional[FeedbackConfig]

    feedback_group_id: Optional[str]

    feedback_source: Optional[FeedbackSource]
    """Feedback from the LangChainPlus App."""

    modified_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    run_id: Optional[str]

    score: Union[float, bool, None]

    session_id: Optional[str]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace_id: Optional[str]

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


FeedbackSource: TypeAlias = Union[
    AppFeedbackSourceParam, APIFeedbackSourceParam, ModelFeedbackSourceParam, AutoEvalFeedbackSourceParam
]
