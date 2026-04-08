"""LangSmith integration for Claude Agent SDK.

This module provides automatic tracing for the Claude Agent SDK by instrumenting
`ClaudeSDKClient` and injecting hooks to trace all tool calls.
"""

import logging
import sys
from typing import Any, Optional

from ._client import instrument_claude_client
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

    Tool tracing is implemented via `PreToolUse` and `PostToolUse` hooks

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

    original = getattr(claude_agent_sdk, "ClaudeSDKClient", None)
    if not original:
        return False

    wrapped = instrument_claude_client(original)
    setattr(claude_agent_sdk, "ClaudeSDKClient", wrapped)

    for module in list(sys.modules.values()):
        try:
            if module and getattr(module, "ClaudeSDKClient", None) is original:
                setattr(module, "ClaudeSDKClient", wrapped)
        except Exception:
            continue

    # Patch create_sdk_mcp_server to wrap tool handlers so that
    # @traceable calls inside them nest under the tool run.
    _patch_create_sdk_mcp_server(claude_agent_sdk)

    return True


def _patch_create_sdk_mcp_server(sdk_module: Any) -> None:
    """Wrap ``create_sdk_mcp_server`` to inject run context into handlers."""
    original_create = getattr(sdk_module, "create_sdk_mcp_server", None)
    if not original_create:
        return
    # Guard against double-patching the same function object.
    if getattr(original_create, "_langsmith_patched", False):
        return

    from ._client import _wrap_tool_handler

    def patched_create(*args: Any, **kwargs: Any) -> Any:
        tools = kwargs.get("tools") or (args[2] if len(args) > 2 else None)
        if tools:
            for tool in tools:
                if hasattr(tool, "handler") and not getattr(
                    tool.handler, "_langsmith_wrapped", False
                ):
                    tool.handler = _wrap_tool_handler(tool.handler)
        return original_create(*args, **kwargs)

    patched_create._langsmith_patched = True  # type: ignore[attr-defined]
    sdk_module.create_sdk_mcp_server = patched_create
