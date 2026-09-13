# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional

from .._models import BaseModel

__all__ = ["DownloadURLResponse"]


class DownloadURLResponse(BaseModel):
    token: str

    download_url: str

    expires_at: Optional[str] = None
    """ExpiresAt is null for a link that never expires."""
