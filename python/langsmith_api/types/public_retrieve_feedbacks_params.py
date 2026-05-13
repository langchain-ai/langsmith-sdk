# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import TypedDict

from .._types import SequenceNotStr
from .source_type import SourceType
from .feedback_level import FeedbackLevel

__all__ = ["PublicRetrieveFeedbacksParams"]


class PublicRetrieveFeedbacksParams(TypedDict, total=False):
    has_comment: Optional[bool]

    has_score: Optional[bool]

    key: Optional[SequenceNotStr[str]]

    level: Optional[FeedbackLevel]
    """Enum for feedback levels."""

    limit: int

    offset: int

    run: Optional[SequenceNotStr[str]]

    session: Optional[SequenceNotStr[str]]

    source: Optional[List[SourceType]]

    user: Optional[SequenceNotStr[str]]
