# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from typing_extensions import TypedDict

__all__ = ["TokenRetrieveParams"]


class TokenRetrieveParams(TypedDict, total=False):
    comment: Optional[str]

    correction: Optional[str]

    score: Union[float, bool, None]

    value: Union[float, bool, str, None]
