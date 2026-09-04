# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

__all__ = ["IssueRetrieveParams"]


class IssueRetrieveParams(TypedDict, total=False):
    include_linear_context: bool
    """
    Include current Linear workflow state and validated linked GitHub pull request
    URLs
    """
