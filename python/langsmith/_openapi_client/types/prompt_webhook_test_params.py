# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["PromptWebhookTestParams", "Payload", "Webhook"]


class PromptWebhookTestParams(TypedDict, total=False):
    payload: Required[Payload]

    webhook: Required[Webhook]
    """Base schema for prompt webhooks."""


class Payload(TypedDict, total=False):
    commit_hash: Required[str]

    created_at: Required[str]

    created_by: Required[str]

    event: Required[Literal["commit", "tag:create", "tag:update"]]
    """Valid trigger types for prompt webhooks."""

    manifest: Required[Dict[str, object]]

    prompt_id: Required[str]

    prompt_name: Required[str]

    tag_name: Optional[str]


class Webhook(TypedDict, total=False):
    """Base schema for prompt webhooks."""

    url: Required[str]
    """URL that receives a POST request with the prompt event payload."""

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
