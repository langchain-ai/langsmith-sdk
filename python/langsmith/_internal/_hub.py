"""Shared constants and helpers for hub (agent/skill) methods."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlencode

from langsmith import utils as ls_utils

REPO_HANDLE_PATTERN = re.compile(r"^[a-z][a-z0-9-_]*$")
PLATFORM_HUB = "/v1/platform/hub/repos"
HUB = "/repos"


def platform_hub_path(api_url: str) -> str:
    """Hub repos path, omitting the ``/v1`` prefix when ``api_url`` ends in it."""
    if api_url.rstrip("/").endswith("/v1"):
        return "/platform/hub/repos"
    return PLATFORM_HUB


def build_commit_url(
    host: str, name: str, commit_hash: str, organization_id: str
) -> str:
    """Build the URL for a hub directory commit."""
    query = urlencode({"organizationId": organization_id})
    return f"{host}/context/{name}/{commit_hash[:8]}?{query}"


def validate_parent_commit(parent_commit: Optional[str]) -> None:
    """Raise ``LangSmithUserError`` if ``parent_commit`` is set but malformed."""
    if parent_commit is not None and not (8 <= len(parent_commit) <= 64):
        raise ls_utils.LangSmithUserError("parent_commit must be 8-64 characters.")
