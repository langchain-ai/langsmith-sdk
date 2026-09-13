# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["BoxGenerateDownloadURLParams"]


class BoxGenerateDownloadURLParams(TypedDict, total=False):
    path: Required[str]

    content_disposition: str

    content_type: str

    expires_in_seconds: int
    """ExpiresInSeconds is optional; a link with no expiry never expires."""
