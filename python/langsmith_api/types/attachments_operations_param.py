# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import TypedDict

from .._types import SequenceNotStr

__all__ = ["AttachmentsOperationsParam"]


class AttachmentsOperationsParam(TypedDict, total=False):
    rename: Dict[str, str]
    """Mapping of old attachment names to new names"""

    retain: SequenceNotStr[str]
    """List of attachment names to keep"""
