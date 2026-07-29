# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["AnnotationQueueRetrieveTotalArchivedParams"]


class AnnotationQueueRetrieveTotalArchivedParams(TypedDict, total=False):
    end_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
