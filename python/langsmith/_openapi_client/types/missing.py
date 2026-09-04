# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal

from pydantic import Field as FieldInfo

from .._models import BaseModel

__all__ = ["Missing"]


class Missing(BaseModel):
    api_missing: Literal["__missing__"] = FieldInfo(alias="__missing__")
