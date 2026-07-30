# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["MissingParam"]


class MissingParam(TypedDict, total=False):
    _missing: Required[Annotated[Literal["__missing__"], PropertyInfo(alias="__missing__")]]
