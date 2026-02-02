"""LangSmith integration for Google ADK (Agent Development Kit).

This module provides automatic tracing for Google ADK by instrumenting
the `Runner` class and injecting callbacks to trace all agent, model,
and tool invocations.
"""

import logging
from typing import Optional

from ._config import set_tracing_config

logger = logging.getLogger(__name__)

__all__ = ["configure_google_adk", "create_traced_session_context"]

# Track if already patched to avoid double-patching
_patched = False


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

    Note: This function can be called before or after importing Runner.
    The patching uses wrapt to modify the original class methods, so
    import order doesn't matter.

    Args:
        name: Name of the root trace. Defaults to "google_adk.session".
        project_name: LangSmith project to trace to.
        metadata: Metadata to associate with all traces.
        tags: Tags to associate with all traces.

    Returns:
        `True` if configuration was successful, `False` otherwise.

    Example:
        >>> from langsmith.integrations.google_adk import configure_google_adk
        >>> from google.adk import Runner  # Can import before configure!
        >>> from google.adk.agents import LlmAgent
        >>>
        >>> configure_google_adk(project_name="my-adk-project")
        >>> # All Runner instances will be traced automatically
    """
    global _patched

    if _patched:
        logger.debug("Google ADK already patched, updating config only")
        set_tracing_config(
            name=name,
            project_name=project_name,
            metadata=metadata,
            tags=tags,
        )
        return True

    try:
        from wrapt import wrap_function_wrapper

        from google.adk import runners  # type: ignore[import-not-found]
    except ImportError as e:
        if "wrapt" in str(e):
            logger.warning("wrapt not installed. Install with: pip install wrapt")
        else:
            logger.warning(
                "Google ADK not installed. Install with: pip install google-adk"
            )
        return False

    # Store the tracing configuration
    set_tracing_config(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
    )

    # Import wrappers here to avoid circular imports
    from ._client import (
        wrap_flow_call_llm_async,
        wrap_runner_init,
        wrap_runner_run,
        wrap_runner_run_async,
    )

    # Patch Runner methods using wrapt (import-order agnostic)
    wrap_function_wrapper(runners, "Runner.__init__", wrap_runner_init)
    wrap_function_wrapper(runners, "Runner.run", wrap_runner_run)
    wrap_function_wrapper(runners, "Runner.run_async", wrap_runner_run_async)

    # Patch BaseLlmFlow._call_llm_async for TTFT capture
    try:
        from google.adk.flows.llm_flows import base_llm_flow

        wrap_function_wrapper(
            base_llm_flow, "BaseLlmFlow._call_llm_async", wrap_flow_call_llm_async
        )
        logger.debug("BaseLlmFlow patched for TTFT capture")
    except ImportError:
        logger.debug("BaseLlmFlow not available, TTFT tracking limited")

    # Patch McpTool if available (MCP is optional)
    try:
        from google.adk.tools.mcp_tool import mcp_tool

        from ._client import wrap_mcp_tool_run_async

        wrap_function_wrapper(mcp_tool, "McpTool.run_async", wrap_mcp_tool_run_async)
        logger.debug("McpTool patched for MCP tracing")
    except ImportError:
        logger.debug("McpTool not available, skipping MCP instrumentation")

    _patched = True
    logger.debug("Google ADK tracing configured successfully")
    return True


def create_traced_session_context(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    inputs: Optional[dict] = None,
):
    """Create a trace context for manual session tracing.

    Use this when you want more control over the tracing context,
    or when using the Runner without the automatic instrumentation.

    Args:
        name: Name of the trace.
        project_name: LangSmith project name.
        metadata: Additional metadata.
        tags: Tags for the trace.
        inputs: Initial inputs for the trace.

    Returns:
        A trace context manager.
    """
    from ._client import create_traced_session_context as _create_context

    return _create_context(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
        inputs=inputs,
    )
