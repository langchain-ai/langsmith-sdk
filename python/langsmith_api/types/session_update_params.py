# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["SessionUpdateParams"]


class SessionUpdateParams(TypedDict, total=False):
    default_dataset_id: Optional[str]

    description: Optional[str]

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    extra: Optional[Dict[str, object]]

    name: Optional[str]

    trace_tier: Optional[Literal["longlived", "shortlived"]]
