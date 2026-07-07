# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from ..._models import BaseModel

__all__ = ["RegistryResponse"]


class RegistryResponse(BaseModel):
    id: Optional[str] = None

    created_at: Optional[str] = None

    created_by: Optional[str] = None

    name: Optional[str] = None

    updated_at: Optional[str] = None

    updated_by: Optional[str] = None

    url: Optional[str] = None
