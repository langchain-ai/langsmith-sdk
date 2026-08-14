"""LangSmith integration for Claude Agent SDK.

This module provides automatic tracing for the Claude Agent SDK by instrumenting
`ClaudeSDKClient` and injecting hooks to trace all tool calls.

Instrumentation is applied **in place** on the original ``ClaudeSDKClient`` class
so that callers who imported the class *before* ``configure_claude_agent_sdk()``
was called still get traced.
"""

import logging
from typing import Optional

from ._client import instrument_claude_client, instrument_sdk_mcp_tool
from ._config import set_tracing_config

logger = logging.getLogger(__name__)

__all__ = ["configure_claude_agent_sdk"]


def configure_claude_agent_sdk(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> bool:
    """Enable LangSmith tracing for the Claude Agent SDK by patching entry points.

    This function instruments the Claude Agent SDK to automatically trace:
    - Chain runs for each conversation stream (via `ClaudeSDKClient`)
    - Model runs for each assistant turn
    - All tool calls including built-in tools, external MCP tools, and SDK MCP tools

    Tool tracing is implemented via `PreToolUse` and `PostToolUse` hooks.

    The class is patched **in place**, so references obtained via
    ``from claude_agent_sdk import ClaudeSDKClient`` before this call
    will still be instrumented.

    Args:
        name: Name of the root trace.
        project_name: LangSmith project to trace to.
        metadata: Metadata to associate with all traces.
        tags: Tags to associate with all traces.

    Returns:
        `True` if configuration was successful, `False` otherwise.

    Example:
        >>> from langsmith.integrations.claude_agent_sdk import (
        ...     configure_claude_agent_sdk,
        ... )
        >>> configure_claude_agent_sdk(
        ...     project_name="my-project", tags=["production"]
        ... )  # doctest: +SKIP
        >>> # Now use claude_agent_sdk as normal - tracing is automatic
    """
    try:
        import claude_agent_sdk  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Claude Agent SDK not installed.")
        return False

    if not hasattr(claude_agent_sdk, "ClaudeSDKClient"):
        logger.warning("Claude Agent SDK missing ClaudeSDKClient.")
        return False

    set_tracing_config(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
    )

    instrument_claude_client(claude_agent_sdk.ClaudeSDKClient)

    # Patch SdkMcpTool so that tool handlers are lazily wrapped with
    # run-context propagation, regardless of import order.
    sdk_mcp_tool_cls = getattr(claude_agent_sdk, "SdkMcpTool", None)
    if sdk_mcp_tool_cls:
        instrument_sdk_mcp_tool(sdk_mcp_tool_cls)

    return True
