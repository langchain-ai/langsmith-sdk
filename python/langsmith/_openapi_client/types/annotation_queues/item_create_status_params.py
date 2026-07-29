# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, TypedDict

__all__ = ["ItemCreateStatusParams"]


class ItemCreateStatusParams(TypedDict, total=False):
    override_added_at: str

    status: Literal["viewed", "completed"]
