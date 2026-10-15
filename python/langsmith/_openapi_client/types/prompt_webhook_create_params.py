# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["PromptWebhookCreateParams"]


class PromptWebhookCreateParams(TypedDict, total=False):
    url: Required[str]
    """URL that receives a POST request with the prompt event payload."""

    id: Optional[str]
    """ID to assign to the webhook. Generated when omitted."""

    exclude_prompts: Optional[SequenceNotStr[str]]
    """IDs of prompts whose events never fire the webhook."""

    headers: Optional[Dict[str, object]]
    """HTTP headers sent with each request, for example an Authorization header.

    Values are stored encrypted and are masked in responses to callers who cannot
    update prompts.
    """

    include_prompts: Optional[SequenceNotStr[str]]
    """IDs of the prompts whose events fire the webhook.

    When empty, events from every prompt in the workspace fire it.
    """

    triggers: List[Literal["commit", "tag:create", "tag:update"]]
    """
    Events that fire the webhook: commit (a new prompt commit), tag:create, and
    tag:update. A webhook with no triggers never fires.
    """
