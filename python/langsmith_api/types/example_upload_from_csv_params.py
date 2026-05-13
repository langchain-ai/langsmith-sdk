# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import FileTypes, SequenceNotStr

__all__ = ["ExampleUploadFromCsvParams"]


class ExampleUploadFromCsvParams(TypedDict, total=False):
    file: Required[FileTypes]

    input_keys: Required[SequenceNotStr[str]]

    metadata_keys: SequenceNotStr[str]

    output_keys: SequenceNotStr[str]
