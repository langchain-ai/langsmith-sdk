# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["VersionRetrieveDiffParams"]


class VersionRetrieveDiffParams(TypedDict, total=False):
    from_version: Required[Annotated[Union[Union[str, datetime], str], PropertyInfo(format="iso8601")]]

    to_version: Required[Annotated[Union[Union[str, datetime], str], PropertyInfo(format="iso8601")]]
