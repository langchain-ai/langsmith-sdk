# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["BoxListServiceURLsResponse"]


class BoxListServiceURLsResponse(BaseModel):
    access: Literal["token", "restricted", "workspace"]
    """
    How the port is shared: "token" for a minted service token, or
    "restricted"/"workspace" for LangSmith login.
    """

    created_at: datetime

    port: int

    created_by: Optional[str] = None
    """The LangSmith user who first shared this port, when known."""

    expires_at: Optional[datetime] = None
    """When the share expires. Set only for "token"; a login grant does not expire."""
