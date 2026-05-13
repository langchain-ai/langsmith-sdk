# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["RunRetrieveLegacyParams"]


class RunRetrieveLegacyParams(TypedDict, total=False):
    exclude_s3_stored_attributes: bool

    exclude_serialized: bool

    include_messages: bool

    session_id: Optional[str]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
