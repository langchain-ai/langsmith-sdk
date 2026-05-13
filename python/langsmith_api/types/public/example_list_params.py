# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo
from ..example_select import ExampleSelect

__all__ = ["ExampleListParams"]


class ExampleListParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    as_of: Annotated[Union[Union[str, datetime], str], PropertyInfo(format="iso8601")]
    """Only modifications made on or before this time are included.

    If None, the latest version of the dataset is used.
    """

    filter: Optional[str]

    limit: int

    metadata: Optional[str]

    offset: int

    select: List[ExampleSelect]
