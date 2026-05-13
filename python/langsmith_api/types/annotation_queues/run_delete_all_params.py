# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from ..._types import SequenceNotStr

__all__ = ["RunDeleteAllParams"]


class RunDeleteAllParams(TypedDict, total=False):
    delete_all: bool

    exclude_run_ids: Optional[SequenceNotStr[str]]

    run_ids: Optional[SequenceNotStr[str]]
