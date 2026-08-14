# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["ServiceURLResponse"]


class ServiceURLResponse(BaseModel):
    token: Optional[str] = None

    browser_url: Optional[str] = None

    expires_at: Optional[str] = None

    service_url: Optional[str] = None
