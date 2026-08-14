# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from ..._models import BaseModel
from .registry_response import RegistryResponse

__all__ = ["RegistryListResponse"]


class RegistryListResponse(BaseModel):
    offset: Optional[int] = None

    registries: Optional[List[RegistryResponse]] = None
