# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo
from .data_type import DataType
from .dataset_transformation_param import DatasetTransformationParam

__all__ = ["DatasetCreateParams"]


class DatasetCreateParams(TypedDict, total=False):
    name: Required[str]

    id: Optional[str]

    created_at: Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]

    data_type: DataType
    """Enum for dataset data types."""

    description: Optional[str]

    externally_managed: Optional[bool]

    extra: Optional[Dict[str, object]]

    inputs_schema_definition: Optional[Dict[str, object]]

    outputs_schema_definition: Optional[Dict[str, object]]

    transformations: Optional[Iterable[DatasetTransformationParam]]
