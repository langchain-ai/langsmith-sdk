# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo
from .timedelta_input_param import TimedeltaInputParam
from .run_stats_group_by_param import RunStatsGroupByParam

__all__ = ["SessionDashboardParams"]


class SessionDashboardParams(TypedDict, total=False):
    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    group_by: Optional[RunStatsGroupByParam]
    """Group by param for run stats."""

    omit_data: bool

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    stride: TimedeltaInputParam
    """Timedelta input."""

    timezone: str

    accept: str
