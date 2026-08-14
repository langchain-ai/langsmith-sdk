"""Integration-agnostic helpers shared by the voice span processors."""

from __future__ import annotations

import json
from typing import Any, Optional


def build_user_message(content: str) -> dict[str, Any]:
    """Build a ``user`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "user", "content": content}


def build_assistant_message(content: str) -> dict[str, Any]:
    """Build an ``assistant`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "assistant", "content": content}


def try_parse_json_object(value: Any) -> Optional[dict]:
    """Return ``value`` parsed as a dict if it's a JSON-object string, else None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None
