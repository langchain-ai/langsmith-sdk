# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, TypedDict

__all__ = ["AutoEvalFeedbackSourceParam"]


class AutoEvalFeedbackSourceParam(TypedDict, total=False):
    """Auto eval feedback source."""

    metadata: Optional[Dict[str, object]]

    type: Literal["auto_eval"]
