# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["AnnotationQueueCreateRunStatusParams"]


class AnnotationQueueCreateRunStatusParams(TypedDict, total=False):
    override_added_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    status: Optional[str]
