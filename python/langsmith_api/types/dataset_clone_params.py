# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo

__all__ = ["DatasetCloneParams"]


class DatasetCloneParams(TypedDict, total=False):
    source_dataset_id: Required[str]

    target_dataset_id: Required[str]

    as_of: Annotated[Union[Union[str, datetime], str, None], PropertyInfo(format="iso8601")]
    """Only modifications made on or before this time are included.

    If None, the latest version of the dataset is used.
    """

    examples: SequenceNotStr[str]

    split: Union[str, SequenceNotStr[str], None]
