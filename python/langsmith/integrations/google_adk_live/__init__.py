"""LangSmith integration for Google ADK Live (Gemini Live voice).

Provides :class:`LangSmithLivePlugin`, an ADK ``BasePlugin`` that traces
``Runner.run_live`` voice conversations. Kept in its own package (and behind the
``google-adk-live`` extra) so that users of the non-streaming
``langsmith.integrations.google_adk`` integration do not take on its
dependencies.

The class is imported lazily so this package can be imported without
``google-adk`` installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._voice import warn_in_development

if TYPE_CHECKING:
    from ._plugin import LangSmithLivePlugin

warn_in_development("google_adk_live")

__all__ = ["LangSmithLivePlugin"]


def __getattr__(name: str) -> Any:
    if name == "LangSmithLivePlugin":
        from ._plugin import LangSmithLivePlugin

        return LangSmithLivePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
