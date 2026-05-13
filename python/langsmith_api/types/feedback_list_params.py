# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .source_type import SourceType
from .feedback_level import FeedbackLevel

__all__ = ["FeedbackListParams"]


class FeedbackListParams(TypedDict, total=False):
    comparative_experiment_id: Optional[str]

    has_comment: Optional[bool]

    has_score: Optional[bool]

    include_user_names: Optional[bool]

    key: Optional[SequenceNotStr[str]]

    level: Optional[FeedbackLevel]
    """Enum for feedback levels."""

    limit: int

    max_created_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    min_created_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    offset: int

    run: Union[SequenceNotStr[str], str, None]

    session: Union[SequenceNotStr[str], str, None]

    source: Optional[List[SourceType]]

    user: Optional[SequenceNotStr[str]]
