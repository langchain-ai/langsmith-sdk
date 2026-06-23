# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["GroupRunsParams"]


class GroupRunsParams(TypedDict, total=False):
    group_by: Required[Literal["run_metadata", "example_metadata"]]

    metadata_key: Required[str]

    session_ids: Required[SequenceNotStr[str]]

    filters: Optional[Dict[str, SequenceNotStr[str]]]

    limit: int

    offset: int

    per_group_limit: int

    preview: bool
