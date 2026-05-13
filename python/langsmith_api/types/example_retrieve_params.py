# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["ExampleRetrieveParams"]


class ExampleRetrieveParams(TypedDict, total=False):
    as_of: Annotated[Union[Union[str, datetime], str], PropertyInfo(format="iso8601")]
    """Only modifications made on or before this time are included.

    If None, the latest version of the dataset is used.
    """

    dataset: Optional[str]
