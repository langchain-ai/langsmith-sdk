"""LangSmith integration for Google ADK (Agent Development Kit)."""

from __future__ import annotations

import logging
from typing import Optional

from ._config import set_tracing_config

logger = logging.getLogger(__name__)

__all__ = ["configure_google_adk", "create_traced_session_context"]

_patched = False


def configure_google_adk(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> bool:
    """Enable LangSmith tracing for Google ADK.

    Can be called before or after importing Runner (import-order agnostic).

    Args:
        name: Name of the root trace. Defaults to "google_adk.session".
        project_name: LangSmith project to trace to.
        metadata: Metadata to associate with all traces.
        tags: Tags to associate with all traces.

    Returns:
        True if configuration was successful, False otherwise.
    """
    global _patched

    if _patched:
        set_tracing_config(
            name=name, project_name=project_name, metadata=metadata, tags=tags
        )
        return True

    try:
        import google.adk  # noqa: F401
        from wrapt import wrap_function_wrapper
    except ImportError as e:
        logger.warning(f"Missing dependency: {e}")
        return False

    set_tracing_config(
        name=name, project_name=project_name, metadata=metadata, tags=tags
    )

    from ._client import (
        wrap_agent_run_async,
        wrap_flow_call_llm_async,
        wrap_runner_run,
        wrap_runner_run_async,
        wrap_tool_run_async,
    )

    _wraps = [
        (
            "google.adk.runners",
            "Runner.run",
            wrap_runner_run,
        ),
        (
            "google.adk.runners",
            "Runner.run_async",
            wrap_runner_run_async,
        ),
        (
            "google.adk.agents.base_agent",
            "BaseAgent.run_async",
            wrap_agent_run_async,
        ),
        (
            "google.adk.flows.llm_flows.base_llm_flow",
            "BaseLlmFlow._call_llm_async",
            wrap_flow_call_llm_async,
        ),
        (
            "google.adk.tools.base_tool",
            "BaseTool.run_async",
            wrap_tool_run_async,
        ),
        (
            "google.adk.tools.function_tool",
            "FunctionTool.run_async",
            wrap_tool_run_async,
        ),
        (
            "google.adk.tools.mcp_tool.mcp_tool",
            "McpTool.run_async",
            wrap_tool_run_async,
        ),
    ]

    for module, name, wrapper in _wraps:
        try:
            wrap_function_wrapper(module, name, wrapper)
        except Exception as e:
            logger.warning(f"Failed to wrap {name}: {e}")

    _patched = True
    return True


def create_traced_session_context(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    inputs: Optional[dict] = None,
):
    """Create a trace context for manual session tracing."""
    from ._client import create_traced_session_context as _create_context

    return _create_context(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
        inputs=inputs,
    )
