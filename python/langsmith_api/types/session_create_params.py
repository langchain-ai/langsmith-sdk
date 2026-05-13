# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["SessionCreateParams"]


class SessionCreateParams(TypedDict, total=False):
    upsert: bool

    id: Optional[str]

    default_dataset_id: Optional[str]

    description: Optional[str]

    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    extra: Optional[Dict[str, object]]

    name: str

    reference_dataset_id: Optional[str]

    start_time: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    trace_tier: Optional[Literal["longlived", "shortlived"]]
