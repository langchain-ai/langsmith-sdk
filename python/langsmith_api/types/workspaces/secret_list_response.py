# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from ..._models import BaseModel

__all__ = ["SecretListResponse", "SecretListResponseItem"]


class SecretListResponseItem(BaseModel):
    key: str


SecretListResponse: TypeAlias = List[SecretListResponseItem]
