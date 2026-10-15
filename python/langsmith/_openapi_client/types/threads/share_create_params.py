# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["ShareCreateParams"]


class ShareCreateParams(TypedDict, total=False):
    project_id: Required[str]
    """project_id is the tracing project UUID containing the thread."""
