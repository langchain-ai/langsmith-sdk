"""LangSmith integration for Google ADK (Agent Development Kit).

This module provides automatic tracing for Google ADK by instrumenting
the `Runner` class and injecting callbacks to trace all agent, model,
and tool invocations.
"""

import logging
import sys
from typing import Optional

from ._client import create_traced_session_context, instrument_adk_runner
from ._config import set_tracing_config

logger = logging.getLogger(__name__)

__all__ = ["configure_google_adk", "create_traced_session_context"]


def configure_google_adk(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> bool:
    """Enable LangSmith tracing for Google ADK by patching entry points.

    This function instruments Google ADK to automatically trace:
    - Chain runs for each agent session (via `Runner`)
    - LLM runs for each model invocation
    - Tool runs for all tool executions
    - Agent runs for sub-agent invocations

    Tracing is implemented via ADK's callback system, which captures:
    - before_agent_callback / after_agent_callback
    - before_model_callback / after_model_callback
    - before_tool_callback / after_tool_callback

    Args:
        name: Name of the root trace. Defaults to "google_adk.session".
        project_name: LangSmith project to trace to.
        metadata: Metadata to associate with all traces.
        tags: Tags to associate with all traces.

    Returns:
        `True` if configuration was successful, `False` otherwise.

    Example:
        >>> from langsmith.integrations.google_adk import configure_google_adk
        >>> configure_google_adk(
        ...     project_name="my-adk-project", tags=["production"]
        ... )  # doctest: +SKIP
        >>> # Now use google.adk as normal - tracing is automatic
        >>> from google.adk.agents import LlmAgent
        >>> from google.adk.runners import Runner
        >>> agent = LlmAgent(name="my_agent", model="gemini-2.0-flash")
        >>> runner = Runner(agent=agent, app_name="my_app")
        >>> # All runs will be traced to LangSmith
    """
    try:
        import google.adk as adk_module  # type: ignore[import-not-found]
        import google.adk.runners as runners_module  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Google ADK not installed. Install with: pip install google-adk")
        return False

    original = getattr(runners_module, "Runner", None)
    if not original:
        logger.warning("Google ADK missing Runner class")
        return False

    # Store the tracing configuration
    set_tracing_config(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
    )

    # Create the traced version
    wrapped = instrument_adk_runner(original)

    # Replace in the runners module
    setattr(runners_module, "Runner", wrapped)

    # Also replace in google.adk module (which re-exports Runner)
    if hasattr(adk_module, "Runner"):
        setattr(adk_module, "Runner", wrapped)

    # Also replace in any modules that have already imported it
    for module in list(sys.modules.values()):
        try:
            if module and getattr(module, "Runner", None) is original:
                setattr(module, "Runner", wrapped)
        except Exception:
            continue

    logger.debug("Google ADK tracing configured successfully")
    return True
