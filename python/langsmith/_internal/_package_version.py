"""Shared helper for resolving an installed package's version.

Integrations stamp ``ls_integration_version`` with the version of the
third-party framework they trace (e.g. ``pipecat-ai``, ``google-adk``,
``openai-agents``) so LangSmith can attribute traces to the integration and
framework version in use. This is the single implementation they all share.
"""

from __future__ import annotations

from functools import cache
from typing import Optional


@cache
def get_package_version(package_name: str) -> Optional[str]:
    """Installed version of ``package_name``, or ``None`` if unresolvable.

    Cached — an installed package's version doesn't change at runtime, and this
    is called once per trace root. Never raises: a missing package or metadata
    just yields ``None``.
    """
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None
