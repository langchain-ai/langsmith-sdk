# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["PromptWebhook"]


class PromptWebhook(BaseModel):
    """Schema for a prompt webhook."""

    id: str

    created_at: datetime

    tenant_id: str

    updated_at: datetime

    url: str
    """URL that receives a POST request with the prompt event payload."""

    exclude_prompts: Optional[List[str]] = None
    """IDs of prompts whose events never fire the webhook."""

    headers: Optional[Dict[str, object]] = None
    """HTTP headers sent with each request, for example an Authorization header.

    Values are stored encrypted and are masked in responses to callers who cannot
    update prompts.
    """

    include_prompts: Optional[List[str]] = None
    """IDs of the prompts whose events fire the webhook.

    When empty, events from every prompt in the workspace fire it.
    """

    triggers: Optional[List[Literal["commit", "tag:create", "tag:update"]]] = None
    """
    Events that fire the webhook: commit (a new prompt commit), tag:create, and
    tag:update. A webhook with no triggers never fires.
    """
