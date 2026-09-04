# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .sandbox_response import SandboxResponse

__all__ = ["SandboxListResponse"]


class SandboxListResponse(BaseModel):
    items: Optional[List[SandboxResponse]] = None
    """This page of sandboxes."""

    next_cursor: Optional[str] = None
    """Cursor for the next page, or null on the last page.

    A non-null value is the only signal that more pages exist. Treat it as opaque.
    """

    offset: Optional[int] = None
    """Deprecated: use next_cursor.

    Offset to request for the next page, or 0 when no pages remain.
    """

    sandboxes: Optional[List[SandboxResponse]] = None
    """Deprecated: use items. Duplicates items."""
