# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["AppHubCrudTenantsTenant"]


class AppHubCrudTenantsTenant(BaseModel):
    id: str

    created_at: datetime

    display_name: str

    tenant_handle: Optional[str] = None
