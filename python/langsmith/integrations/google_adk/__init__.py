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
        from google.adk import runners  # type: ignore[import-untyped]
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

    # Runner wrappers
    wrap_function_wrapper(runners, "Runner.run", wrap_runner_run)
    wrap_function_wrapper(runners, "Runner.run_async", wrap_runner_run_async)

    # Agent wrapper — BaseAgent.run_async is @final, catches all subclasses
    try:
        from google.adk.agents import base_agent  # type: ignore[import-untyped]

        wrap_function_wrapper(
            base_agent, "BaseAgent.run_async", wrap_agent_run_async
        )
    except ImportError:
        pass

    # Tool wrappers — subclasses override run_async, so wrap each
    try:
        from google.adk.tools import base_tool  # type: ignore[import-untyped]

        wrap_function_wrapper(
            base_tool, "BaseTool.run_async", wrap_tool_run_async
        )
    except ImportError:
        pass

    try:
        from google.adk.tools import function_tool  # type: ignore[import-untyped]

        wrap_function_wrapper(
            function_tool, "FunctionTool.run_async", wrap_tool_run_async
        )
    except ImportError:
        pass

    try:
        from google.adk.tools.mcp_tool import mcp_tool  # type: ignore[import-untyped]

        wrap_function_wrapper(
            mcp_tool, "McpTool.run_async", wrap_tool_run_async
        )
    except ImportError:
        pass

    # LLM flow wrapper
    try:
        from google.adk.flows.llm_flows import (  # type: ignore[import-untyped]
            base_llm_flow,
        )

        wrap_function_wrapper(
            base_llm_flow, "BaseLlmFlow._call_llm_async", wrap_flow_call_llm_async
        )
    except ImportError:
        pass

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
