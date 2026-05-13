# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from ..._types import SequenceNotStr

__all__ = ["BulkDeleteParams"]


class BulkDeleteParams(TypedDict, total=False):
    example_ids: Required[SequenceNotStr[str]]
    """ExampleIDs is a list of UUIDs identifying the examples to delete."""

    hard_delete: Required[bool]
    """
    HardDelete indicates whether to perform a hard delete. Currently only True is
    supported.
    """
