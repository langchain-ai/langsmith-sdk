# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from ..._types import SequenceNotStr

__all__ = ["ItemDeleteAllParams"]


class ItemDeleteAllParams(TypedDict, total=False):
    item_ids: SequenceNotStr[str]
