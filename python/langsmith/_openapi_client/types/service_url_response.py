# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ServiceURLResponse"]


class ServiceURLResponse(BaseModel):
    token: Optional[str] = None
    """Token and ExpiresAt are empty in LangSmith login mode (no token is minted)."""

    access: Optional[Literal["restricted", "workspace"]] = None
    """
    Access echoes the enabled LangSmith login level ("restricted"/"workspace");
    omitted in token mode.
    """

    browser_url: Optional[str] = None

    expires_at: Optional[str] = None

    service_url: Optional[str] = None
