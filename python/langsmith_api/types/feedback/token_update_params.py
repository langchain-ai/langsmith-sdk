# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import TypedDict

__all__ = ["TokenUpdateParams"]


class TokenUpdateParams(TypedDict, total=False):
    comment: Optional[str]

    correction: Union[Dict[str, object], str, None]

    metadata: Optional[Dict[str, object]]

    score: Union[float, bool, None]

    value: Union[float, bool, str, None]
