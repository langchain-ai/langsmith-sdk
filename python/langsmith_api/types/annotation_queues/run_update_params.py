# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RunUpdateParams"]


class RunUpdateParams(TypedDict, total=False):
    queue_id: Required[str]

    added_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    last_reviewed_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
