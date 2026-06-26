# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RegistryUpdateParams"]


class RegistryUpdateParams(TypedDict, total=False):
    body_name: Annotated[str, PropertyInfo(alias="name")]

    password: str

    url: str

    username: str
