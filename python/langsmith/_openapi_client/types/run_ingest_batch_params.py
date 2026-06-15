# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import TypedDict

from .run_param import RunParam

__all__ = ["RunIngestBatchParams"]


class RunIngestBatchParams(TypedDict, total=False):
    patch: Iterable[RunParam]

    post: Iterable[RunParam]
