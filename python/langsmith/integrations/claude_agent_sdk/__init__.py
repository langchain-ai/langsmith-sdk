"""LangSmith integration for Claude Agent SDK.

This module provides automatic tracing for the Claude Agent SDK by instrumenting
key components like ClaudeSDKClient, SdkMcpTool, and tool handlers.
"""

import logging
import sys
from typing import Optional

from ._client import instrument_claude_client
from ._config import set_tracing_config
from ._tools import instrument_sdk_mcp_tool_class, instrument_tool_factory

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
    - Chain runs for each conversation stream (via ClaudeSDKClient)
    - Model runs for each assistant turn
    - Tool calls made during agent execution

    Args:
        name: Name of the root trace.
        project_name: LangSmith project to trace to.
        metadata: Metadata to associate with all traces.
        tags: Tags to associate with all traces.

    Returns:
        True if configuration was successful, False otherwise.

    Example:
        >>> from langsmith.integrations.claude_agents_sdk import (
        ...     configure_claude_agent_sdk,
        ... )
        >>> configure_claude_agent_sdk(project_name="my-project", tags=["production"])
        >>> # Now use claude_agent_sdk as normal - tracing is automatic
    """
    try:
        import claude_agent_sdk  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("Claude Agent SDK not installed.")
        return False

    required = ["ClaudeSDKClient", "SdkMcpTool", "tool"]
    if not all(hasattr(claude_agent_sdk, attr) for attr in required):
        logger.warning("Claude Agent SDK missing expected attributes.")
        return False

    set_tracing_config(
        name=name,
        project_name=project_name,
        metadata=metadata,
        tags=tags,
    )

    patches = {
        "ClaudeSDKClient": instrument_claude_client,
        "SdkMcpTool": instrument_sdk_mcp_tool_class,
        "tool": instrument_tool_factory,
    }

    for symbol, wrapper in patches.items():
        original = getattr(claude_agent_sdk, symbol, None)
        if not original:
            continue
        wrapped = wrapper(original)
        setattr(claude_agent_sdk, symbol, wrapped)

        # Best-effort propagation to already-imported modules.
        for module in list(sys.modules.values()):
            try:
                if module and getattr(module, symbol, None) is original:
                    setattr(module, symbol, wrapped)
            except Exception:
                continue

    return True
