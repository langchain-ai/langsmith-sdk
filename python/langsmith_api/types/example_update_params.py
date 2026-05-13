# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import TypedDict

from .._types import SequenceNotStr
from .attachments_operations_param import AttachmentsOperationsParam

__all__ = ["ExampleUpdateParams"]


class ExampleUpdateParams(TypedDict, total=False):
    attachments_operations: Optional[AttachmentsOperationsParam]

    dataset_id: Optional[str]

    inputs: Optional[Dict[str, object]]

    metadata: Optional[Dict[str, object]]

    outputs: Optional[Dict[str, object]]

    overwrite: bool

    split: Union[SequenceNotStr[str], str, None]
