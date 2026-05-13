# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["ExampleCreateParams"]


class ExampleCreateParams(TypedDict, total=False):
    dataset_id: Required[str]

    id: Optional[str]

    created_at: str

    inputs: Optional[Dict[str, object]]

    metadata: Optional[Dict[str, object]]

    outputs: Optional[Dict[str, object]]

    source_run_id: Optional[str]

    split: Union[SequenceNotStr[str], str, None]

    use_legacy_message_format: bool
    """Use Legacy Message Format for LLM runs"""

    use_source_run_attachments: SequenceNotStr[str]

    use_source_run_io: bool
