"""Shared constants and helpers for hub (agent/skill) methods."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlencode

from langsmith import utils as ls_utils

REPO_HANDLE_PATTERN = re.compile(r"^[a-z][a-z0-9-_]*$")
PLATFORM_HUB = "/v1/platform/hub/repos"
HUB = "/repos"

_FLAT_HUB_PROMPT_TAGS = frozenset(
    {"StructuredPrompt", "ChatPromptTemplate", "PromptTemplate"}
)
_WRAPPED_HUB_PROMPT_TAGS = frozenset({"PromptPlayground", "RunnableSequence"})


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


def _hub_manifest_tag(manifest: dict[str, Any]) -> Optional[str]:
    id_ = manifest.get("id")
    if not isinstance(id_, list) or not id_:
        return None
    tag = id_[-1]
    return tag if isinstance(tag, str) else None


def _default_hub_model_manifest() -> dict[str, Any]:
    return {
        "id": ["langchain", "schema", "runnable", "RunnableBinding"],
        "lc": 1,
        "type": "constructor",
        "kwargs": {
            "bound": {
                "id": ["langchain", "chat_models", "openai", "ChatOpenAI"],
                "lc": 1,
                "type": "constructor",
                "kwargs": {
                    "openai_api_key": {
                        "id": ["OPENAI_API_KEY"],
                        "lc": 1,
                        "type": "secret",
                    }
                },
            },
            "kwargs": {},
        },
    }


def wrap_manifest_for_hub_push(manifest: dict[str, Any]) -> dict[str, Any]:
    """Wrap flat prompt manifests in PromptPlayground format for Hub commits."""
    tag = _hub_manifest_tag(manifest)
    if tag in _WRAPPED_HUB_PROMPT_TAGS:
        return manifest
    if manifest.get("lc") != 1 or manifest.get("type") != "constructor":
        return manifest
    if tag not in _FLAT_HUB_PROMPT_TAGS:
        return manifest
    return {
        "lc": 1,
        "type": "constructor",
        "id": ["langsmith", "playground", "PromptPlayground"],
        "kwargs": {
            "first": manifest,
            "last": _default_hub_model_manifest(),
        },
    }
