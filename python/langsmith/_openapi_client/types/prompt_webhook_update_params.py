# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Optional
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["PromptWebhookUpdateParams"]


class PromptWebhookUpdateParams(TypedDict, total=False):
    exclude_prompts: Optional[SequenceNotStr[str]]
    """IDs of prompts whose events never fire the webhook, replacing the current list.

    Omit to keep it.
    """

    headers: Optional[Dict[str, object]]
    """HTTP headers sent with each request, replacing all current headers.

    Omit to keep them. Masked values (**\\**\\**\\**\\****) from a read are rejected.
    """

    include_prompts: Optional[SequenceNotStr[str]]
    """IDs of the prompts whose events fire the webhook, replacing the current list.

    Omit to keep it.
    """

    triggers: Optional[List[Literal["commit", "tag:create", "tag:update"]]]
    """
    Events that fire the webhook (commit, tag:create, tag:update), replacing the
    current list. Omit to keep it.
    """

    url: Optional[str]
    """URL that receives the POST requests. Omit to keep the current URL."""
