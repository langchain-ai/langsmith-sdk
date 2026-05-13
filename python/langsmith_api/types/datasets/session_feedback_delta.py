# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List

from ..._models import BaseModel

__all__ = ["SessionFeedbackDelta", "FeedbackDeltas"]


class FeedbackDeltas(BaseModel):
    """Feedback key with number of improvements and regressions."""

    improved_examples: List[str]

    regressed_examples: List[str]


class SessionFeedbackDelta(BaseModel):
    """List of feedback keys with number of improvements and regressions for each."""

    feedback_deltas: Dict[str, FeedbackDeltas]
