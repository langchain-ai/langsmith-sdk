# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .._types import FileTypes, SequenceNotStr
from .data_type import DataType

__all__ = ["DatasetUploadParams"]


class DatasetUploadParams(TypedDict, total=False):
    file: Required[FileTypes]

    input_keys: Required[SequenceNotStr[str]]

    data_type: DataType
    """Enum for dataset data types."""

    description: Optional[str]

    input_key_mappings: Optional[str]

    inputs_schema_definition: Optional[str]

    metadata_key_mappings: Optional[str]

    metadata_keys: SequenceNotStr[str]

    name: Optional[str]

    output_key_mappings: Optional[str]

    output_keys: SequenceNotStr[str]

    outputs_schema_definition: Optional[str]

    transformations: Optional[str]
