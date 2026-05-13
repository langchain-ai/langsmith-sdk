# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["FeedbackRetrieveParams"]


class FeedbackRetrieveParams(TypedDict, total=False):
    include_user_names: Optional[bool]
