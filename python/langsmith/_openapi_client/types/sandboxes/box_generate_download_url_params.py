# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List
from typing_extensions import Literal, Required, TypedDict

__all__ = ["BoxGenerateDownloadURLParams"]


class BoxGenerateDownloadURLParams(TypedDict, total=False):
    path: Required[str]

    content_disposition: str

    content_type: str

    csp_sandbox_flags: List[
        Literal[
            "allow-downloads",
            "allow-forms",
            "allow-modals",
            "allow-orientation-lock",
            "allow-pointer-lock",
            "allow-popups",
            "allow-presentation",
            "allow-scripts",
            "allow-top-navigation-by-user-activation",
        ]
    ]
    """
    CSPSandboxFlags loosen the CSP sandbox the file is served under; omit for the
    most restrictive policy.
    """

    csp_source_bundles: List[Literal["cdnjs", "google-fonts", "jsdelivr", "unpkg", "none"]]
    """
    CSPSourceBundles allow the served file to fetch from named third-party origins;
    omit to send no fetch directive.
    """

    expires_in_seconds: int
    """ExpiresInSeconds is optional; a link with no expiry never expires."""
