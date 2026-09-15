# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["SandboxListUsageCostsParams"]


class SandboxListUsageCostsParams(TypedDict, total=False):
    end_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Exclusive RFC3339 end time; the range must not exceed 31 days"""

    start_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Inclusive RFC3339 start time"""

    cursor: str
    """Opaque pagination cursor"""

    page_size: int
    """Maximum rows to return"""

    resource_ids: SequenceNotStr[str]
    """Resource UUID filter; repeat this parameter up to 100 times"""

    resource_type: Literal["SANDBOX", "SNAPSHOT"]
    """Resource type filter"""
