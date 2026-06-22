# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["InsightUpdateParams"]


class InsightUpdateParams(TypedDict, total=False):
    session_id: Required[str]

    name: Required[str]
