# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["ConfigDeleteParams"]


class ConfigDeleteParams(TypedDict, total=False):
    feedback_key: Required[str]
