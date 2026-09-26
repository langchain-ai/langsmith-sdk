# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, TypedDict

__all__ = ["BoxGenerateServiceURLParams"]


class BoxGenerateServiceURLParams(TypedDict, total=False):
    access: Literal["restricted", "workspace", "off"]
    """
    Access selects the login mode, mutually exclusive with the minted token. Omit
    the field for token mode: mint a short-lived service token (default).
    "restricted" — LangSmith login: any user with SandboxesRead on the sandbox.
    "workspace" — LangSmith login: any member of the owning workspace. "off" —
    remove an existing LangSmith login grant and mint a token. A LangSmith login
    grant is durable; token mode is refused (409) while one exists.
    """

    expires_in_seconds: int

    port: int
