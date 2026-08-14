# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["RegistryListParams"]


class RegistryListParams(TypedDict, total=False):
    limit: int
    """Maximum number of registries to return"""

    name_contains: str
    """Filter to registries whose name contains this substring"""

    offset: int
    """Number of registries to skip"""
