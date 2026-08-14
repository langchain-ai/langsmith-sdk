# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["ShareDeleteParams"]


class ShareDeleteParams(TypedDict, total=False):
    session_id: str
    """session_id is the tracing project UUID containing the trace."""
