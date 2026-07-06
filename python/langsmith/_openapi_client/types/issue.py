# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["Issue"]


class Issue(BaseModel):
    id: Optional[str] = None

    actions: Optional[object] = None

    created_at: Optional[str] = None

    description: Optional[str] = None

    first_seen_at: Optional[str] = None

    fix_branch: Optional[str] = None

    fix_dispatched_at: Optional[str] = None

    fix_pr_number: Optional[int] = None

    fix_prompt: Optional[str] = None

    fix_verification: Optional[object] = None

    last_seen_at: Optional[str] = None

    name: Optional[str] = None

    proposed_context_fixes: Optional[List[object]] = None

    proposed_examples: Optional[List[object]] = None

    proposed_fix: Optional[str] = None

    proposed_prompt_fixes: Optional[List[object]] = None

    session_id: Optional[str] = None

    severity: Optional[Literal[0, 1, 2, 3]] = None

    status: Optional[Literal["open", "completed", "ignored"]] = None

    tags: Optional[List[str]] = None

    tenant_id: Optional[str] = None

    traces: Optional[object] = None

    updated_at: Optional[str] = None
