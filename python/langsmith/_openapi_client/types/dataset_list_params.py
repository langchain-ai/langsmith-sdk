# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from typing_extensions import Literal, Annotated, TypedDict

from .._types import SequenceNotStr
from .._utils import PropertyInfo
from .data_type import DataType
from .sort_by_dataset_column import SortByDatasetColumn

__all__ = ["DatasetListParams"]


class DatasetListParams(TypedDict, total=False):
    id: Optional[SequenceNotStr[str]]

    datatype: Annotated[Union[List[DataType], DataType, None], PropertyInfo(alias="data_type")]
    """Enum for dataset data types."""

    exclude: Optional[List[Literal["example_count"]]]

    exclude_corrections_datasets: bool

    limit: int

    metadata: Optional[str]

    name: Optional[str]

    name_contains: Optional[str]

    offset: int

    sort_by: SortByDatasetColumn
    """Enum for available dataset columns to sort by."""

    sort_by_desc: bool

    tag_value_id: Optional[SequenceNotStr[str]]
