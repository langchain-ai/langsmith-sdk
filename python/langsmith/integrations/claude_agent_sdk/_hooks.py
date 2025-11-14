"""Hook-based tool tracing for Claude Agent SDK.

This module provides hook handlers that traces tool calls by intercepting
PreToolUse and PostToolUse events.
"""

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from langsmith.run_helpers import get_current_run_tree
from langsmith.run_trees import RunTree

from ._tools import get_parent_run_tree

if TYPE_CHECKING:
    from claude_agent_sdk import (
        HookContext,
        HookInput,
        HookJSONOutput,
    )

logger = logging.getLogger(__name__)

# Storage for correlating PreToolUse and PostToolUse events
# Key: tool_use_id, Value: (run_tree, start_time)
_active_tool_runs: dict[str, tuple[Any, float]] = {}

# Storage for subagent names
# Key: tool_use_id, Value: subagent_name
_subagent_names: dict[str, str] = {}

# Storage for active subagent session runs
# Key: tool_use_id (of the Task tool), Value: run_tree for the subagent session
_subagent_sessions: dict[str, RunTree] = {}

# Storage for tool runs created by subagents (managed by client, not hooks)
# Key: tool_use_id, Value: run_tree for the tool
_subagent_tool_runs: dict[str, tuple[RunTree, float]] = {}


async def pre_tool_use_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Trace tool execution before it starts.

    Args:
        input_data: Contains tool_name, tool_input, session_id
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context (currently contains only signal)

    Returns:
        Hook output (empty dict allows execution to proceed)
    """
    if not tool_use_id:
        logger.debug("PreToolUse hook called without tool_use_id, skipping trace")
        return {}

    tool_name: str = str(input_data.get("tool_name", "unknown_tool"))
    tool_input = input_data.get("tool_input", {})

    # Track subagent name if this is a Task tool (subagent invocation)
    if tool_use_id and tool_name == "Task" and tool_input:
        # Extract subagent name from input
        # Try subagent_type first, then description, then fall back to generic name
        subagent_name = (
            tool_input.get("subagent_type")
            or (tool_input.get("description", "").split()[0] if tool_input.get("description") else None)
            or "unknown-agent"
        )
        _subagent_names[tool_use_id] = subagent_name
        logger.debug(f"Tracked subagent name: '{subagent_name}' (id={tool_use_id})")

    # Skip if this tool run was already created by the client (for subagent tools)
    if tool_use_id in _subagent_tool_runs:
        logger.debug(f"Tool {tool_name} (id={tool_use_id}) already tracked by client, skipping hook")
        return {}

    try:
        parent = get_parent_run_tree() or get_current_run_tree()
        if not parent:
            logger.debug(f"No parent run tree found for tool {tool_name}")
            return {}

        start_time = time.time()
        tool_run = parent.create_child(
            name=tool_name,
            run_type="tool",
            inputs={"input": tool_input} if tool_input else {},
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )

        try:
            tool_run.post()
        except Exception as e:
            logger.warning(f"Failed to post tool run for {tool_name}: {e}")

        _active_tool_runs[tool_use_id] = (tool_run, start_time)

        logger.debug(f"Started tool trace for {tool_name} (id={tool_use_id})")

        # If this is a Task tool, create a subagent session run
        if tool_name == "Task" and tool_use_id in _subagent_names:
            subagent_name = _subagent_names[tool_use_id]
            try:
                subagent_session_run = tool_run.create_child(
                    name=subagent_name,
                    run_type="chain",
                    start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
                )
                # Don't post yet - wait until we have inputs and outputs
                _subagent_sessions[tool_use_id] = subagent_session_run
                logger.debug(f"Created subagent session for {subagent_name} (id={tool_use_id})")
            except Exception as e:
                logger.warning(f"Failed to create subagent session for {subagent_name}: {e}")

    except Exception as e:
        logger.warning(f"Error in PreToolUse hook for {tool_name}: {e}", exc_info=True)

    return {}


async def post_tool_use_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Trace tool execution after it completes.

    Args:
        input_data: Contains tool_name, tool_input, tool_response, session_id, etc.
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context (currently contains only signal)

    Returns:
        Hook output (empty dict by default)
    """
    if not tool_use_id:
        logger.debug("PostToolUse hook called without tool_use_id, skipping trace")
        return {}

    tool_name: str = str(input_data.get("tool_name", "unknown_tool"))
    tool_response = input_data.get("tool_response")

    # Check if this is a subagent tool managed by the client
    subagent_tool_info = _subagent_tool_runs.pop(tool_use_id, None)
    if subagent_tool_info:
        # This tool run was created by the client, update it with response
        tool_run, start_time = subagent_tool_info
        try:
            if isinstance(tool_response, dict):
                outputs = tool_response
            elif isinstance(tool_response, list):
                outputs = {"content": tool_response}
            else:
                outputs = {"output": str(tool_response)} if tool_response else {}

            is_error = False
            if isinstance(tool_response, dict):
                is_error = tool_response.get("is_error", False)

            tool_run.end(
                outputs=outputs,
                error=outputs.get("output") if is_error else None,
            )
            tool_run.patch()
            logger.debug(f"Updated subagent tool {tool_name} (id={tool_use_id}) with response")
        except Exception as e:
            logger.warning(f"Failed to update subagent tool run: {e}")
        return {}

    try:
        run_info = _active_tool_runs.pop(tool_use_id, None)
        if not run_info:
            logger.debug(
                f"No matching PreToolUse found for {tool_name} (id={tool_use_id})"
            )
            return {}

        tool_run, start_time = run_info

        if isinstance(tool_response, dict):
            outputs = tool_response
        elif isinstance(tool_response, list):
            outputs = {"content": tool_response}
        else:
            outputs = {"output": str(tool_response)} if tool_response else {}

        # Check if the tool execution was an error
        is_error = False
        if isinstance(tool_response, dict):
            is_error = tool_response.get("is_error", False)

        # If this was a Task tool, complete the subagent session first
        subagent_session = _subagent_sessions.pop(tool_use_id, None)
        if subagent_session:
            try:
                subagent_session.end(
                    outputs=outputs,
                    error=outputs.get("output") if is_error else None,
                )
                # Post everything at once (inputs, outputs, end_time)
                subagent_session.post()
                logger.debug(f"Completed subagent session for {subagent_session.name}")
            except Exception as e:
                logger.warning(f"Failed to complete subagent session: {e}", exc_info=True)

        tool_run.end(
            outputs=outputs,
            error=outputs.get("output") if is_error else None,
        )

        try:
            tool_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch tool run for {tool_name}: {e}")

        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            f"Completed tool trace for {tool_name} "
            f"(id={tool_use_id}, duration={duration_ms:.2f}ms)"
        )

    except Exception as e:
        logger.warning(f"Error in PostToolUse hook for {tool_name}: {e}", exc_info=True)

    return {}


def clear_active_tool_runs() -> None:
    """Clear all active tool runs.

    This should be called when a conversation ends to avoid memory leaks
    and to clean up any orphaned tool runs.
    """
    global _active_tool_runs, _subagent_names, _subagent_sessions, _subagent_tool_runs

    # End any orphaned subagent sessions first
    for tool_use_id, subagent_session in _subagent_sessions.items():
        try:
            subagent_session.end(error="Subagent session not completed (conversation ended)")
            subagent_session.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned subagent session {tool_use_id}: {e}")

    # End any orphaned subagent tool runs
    for tool_use_id, (tool_run, _) in _subagent_tool_runs.items():
        try:
            tool_run.end(error="Tool run not completed (conversation ended)")
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned subagent tool run {tool_use_id}: {e}")

    # End any orphaned tool runs
    for tool_use_id, (tool_run, _) in _active_tool_runs.items():
        try:
            tool_run.end(error="Tool run not completed (conversation ended)")
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned tool run {tool_use_id}: {e}")

    _active_tool_runs.clear()
    _subagent_names.clear()
    _subagent_sessions.clear()
    _subagent_tool_runs.clear()
