# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, TypedDict

__all__ = ["ModelFeedbackSourceParam"]


class ModelFeedbackSourceParam(TypedDict, total=False):
    """Model feedback source."""

    metadata: Optional[Dict[str, object]]

    type: Literal["model"]
