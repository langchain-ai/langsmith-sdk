"""Configuration for Google ADK tracing."""

from __future__ import annotations

from typing import Any, Optional

_tracing_config: dict[str, Any] = {
    "name": None,
    "project_name": None,
    "metadata": None,
    "tags": None,
}


def set_tracing_config(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> None:
    global _tracing_config
    _tracing_config = {
        "name": name,
        "project_name": project_name,
        "metadata": metadata,
        "tags": tags,
    }


def get_tracing_config() -> dict[str, Any]:
    return _tracing_config.copy()
