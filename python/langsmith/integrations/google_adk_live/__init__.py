"""LangSmith integration for Google ADK Live (Gemini Live voice).

Provides :class:`LangSmithGoogleADKLivePlugin`, an ADK ``BasePlugin`` that traces
``Runner.run_live`` voice conversations. Kept in its own package (and behind the
``google-adk-live`` extra) so that users of the non-streaming
``langsmith.integrations.google_adk`` integration do not take on its
dependencies.

The class is imported lazily so this package can be imported without
``google-adk`` installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langsmith.integrations.google_adk_live._plugin import (
        LangSmithGoogleADKLivePlugin,
    )

__all__ = ["LangSmithGoogleADKLivePlugin"]


def __getattr__(name: str) -> Any:
    if name == "LangSmithGoogleADKLivePlugin":
        from langsmith.integrations.google_adk_live._plugin import (
            LangSmithGoogleADKLivePlugin,
        )

        return LangSmithGoogleADKLivePlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
