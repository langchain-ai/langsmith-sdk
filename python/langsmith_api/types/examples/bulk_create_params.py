# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["BulkCreateParams", "Body"]


class BulkCreateParams(TypedDict, total=False):
    body: Required[Iterable[Body]]
    """Schema for a batch of examples to be created."""


class Body(TypedDict, total=False):
    """
    Example with optional created_at to prevent duplicate versions in bulk operations.
    """

    dataset_id: Required[str]

    id: Optional[str]

    created_at: Optional[str]

    inputs: Optional[Dict[str, object]]

    metadata: Optional[Dict[str, object]]

    outputs: Optional[Dict[str, object]]

    source_run_id: Optional[str]

    split: Union[SequenceNotStr[str], str, None]

    use_legacy_message_format: bool
    """Use Legacy Message Format for LLM runs"""

    use_source_run_attachments: SequenceNotStr[str]

    use_source_run_io: bool
