# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = ["RunRetrieveParams"]


class RunRetrieveParams(TypedDict, total=False):
    share_token: Required[str]

    selects: Required[SequenceNotStr[str]]
    """repeatable public run fields to include"""

    start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Run start_time coordinate (RFC3339)"""

    accept: Annotated[str, PropertyInfo(alias="Accept")]
