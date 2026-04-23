"""Shared constants and helpers for hub (agent/skill) methods.

Kept in an internal module so both ``Client`` and ``AsyncClient`` can depend
on them without creating an import edge between the two clients.
"""

from __future__ import annotations

import re
from typing import Optional

from langsmith import utils as ls_utils

REPO_HANDLE_PATTERN = re.compile(r"^[a-z][a-z0-9-_]*$")
PLATFORM_HUB = "/v1/platform/hub/repos"
HUB = "/repos"


def build_context_url(host: str, owner: str, name: str, commit_hash: str) -> str:
    """Build a URL for a pushed hub context commit."""
    return f"{host}/hub/{owner}/{name}:{commit_hash[:8]}"


def validate_parent_commit(parent_commit: Optional[str]) -> None:
    """Raise ``LangSmithUserError`` if ``parent_commit`` is set but malformed."""
    if parent_commit is not None and not (8 <= len(parent_commit) <= 64):
        raise ls_utils.LangSmithUserError(
            "parent_commit must be 8-64 characters."
        )
