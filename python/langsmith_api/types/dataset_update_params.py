# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import TypeAlias, TypedDict

from .._types import SequenceNotStr
from .missing_param import MissingParam
from .attachments_operations_param import AttachmentsOperationsParam
from .dataset_transformation_param import DatasetTransformationParam

__all__ = [
    "DatasetUpdateParams",
    "BaselineExperimentID",
    "Description",
    "InputsSchemaDefinition",
    "Metadata",
    "Name",
    "OutputsSchemaDefinition",
    "PatchExamples",
    "Transformations",
]


class DatasetUpdateParams(TypedDict, total=False):
    baseline_experiment_id: Optional[BaselineExperimentID]

    description: Optional[Description]

    inputs_schema_definition: Optional[InputsSchemaDefinition]

    metadata: Optional[Metadata]

    name: Optional[Name]

    outputs_schema_definition: Optional[OutputsSchemaDefinition]

    patch_examples: Optional[Dict[str, PatchExamples]]

    transformations: Optional[Transformations]


BaselineExperimentID: TypeAlias = Union[str, MissingParam]

Description: TypeAlias = Union[str, MissingParam]

InputsSchemaDefinition: TypeAlias = Union[Dict[str, object], MissingParam]

Metadata: TypeAlias = Union[Dict[str, object], MissingParam]

Name: TypeAlias = Union[str, MissingParam]

OutputsSchemaDefinition: TypeAlias = Union[Dict[str, object], MissingParam]


class PatchExamples(TypedDict, total=False):
    """Update class for Example."""

    attachments_operations: Optional[AttachmentsOperationsParam]

    dataset_id: Optional[str]

    inputs: Optional[Dict[str, object]]

    metadata: Optional[Dict[str, object]]

    outputs: Optional[Dict[str, object]]

    overwrite: bool

    split: Union[SequenceNotStr[str], str, None]


Transformations: TypeAlias = Union[Iterable[DatasetTransformationParam], MissingParam]
