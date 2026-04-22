"""Hook-based tool tracing for Claude Agent SDK.

All mutable state is module-level. This is intentional: hook functions are
registered once and called by the SDK's event loop, so they need stable
references to shared state. The trade-off is that concurrent
``receive_response()`` calls on separate ``ClaudeSDKClient`` instances would
corrupt each other's state. In practice this is fine — the SDK client is
single-session.
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

# ── Module-level state ────────────────────────────────────────────────────────

# Key: tool_use_id → (run_tree, start_time)
_active_tool_runs: dict[str, tuple[Any, float]] = {}

# Key: agent_id → RunTree for the subagent chain.
# Populated by SubagentStart, consumed by SubagentStop.
_subagent_runs: dict[str, RunTree] = {}

# Key: tool_use_id → tool_input dict.
# When PreToolUse fires for an "Agent" tool, it stashes here.
# SubagentStart pops it to find the matching Agent tool run.
_pending_agent_tools: dict[str, dict[str, Any]] = {}

# Key: agent_id → Agent tool_use_id.
# Maps a subagent back to the Agent tool that spawned it.
_agent_to_tool_mapping: dict[str, str] = {}

# Key: Agent tool_use_id → RunTree.
# SubagentStop moves the run here; PostToolUse sets outputs on it;
# clear_active_tool_runs() ends + patches it.
_ended_subagent_runs: dict[str, RunTree] = {}

# (transcript_path, subagent_RunTree) captured from SubagentStop.
# Used for usage extraction and creating missing LLM runs.
_subagent_transcript_paths: list[tuple[str, "RunTree"]] = []

# Main session transcript path, captured from BaseHookInput.transcript_path
# on the first hook that fires (every hook inherits this field).
_main_transcript_path: Optional[str] = None


# ── Public helpers (used by _client.py) ───────────────────────────────────────


def get_subagent_run_by_tool_id(tool_use_id: str) -> Optional[RunTree]:
    """Get a subagent run by the Agent tool's tool_use_id.

    Checks both active subagent runs and ended-but-not-finalised runs,
    because the SDK fires ``SubagentStop`` before the subagent's messages
    reach the client.
    """
    # Check active subagents first
    for aid, tid in _agent_to_tool_mapping.items():
        if tid == tool_use_id:
            return _subagent_runs.get(aid)
    # Fall back to ended-but-not-finalised subagents
    return _ended_subagent_runs.get(tool_use_id)


# ── Hook functions ────────────────────────────────────────────────────────────


async def pre_tool_use_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Trace tool execution before it starts.

    Args:
        input_data: Contains `tool_name`, `tool_input`, `session_id`, `agent_id`
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context (currently contains only signal)

    Returns:
        Hook output (empty dict allows execution to proceed)
    """
    if not tool_use_id:
        return {}

    global _main_transcript_path
    data: dict[str, Any] = dict(input_data)  # flatten TypedDict union
    tool_name: str = str(data.get("tool_name", "unknown_tool"))
    tool_input: dict[str, Any] = dict(data.get("tool_input") or {})
    agent_id: Optional[str] = str(data["agent_id"]) if data.get("agent_id") else None

    # Capture main session transcript path from BaseHookInput
    if _main_transcript_path is None and data.get("transcript_path"):
        _main_transcript_path = str(data["transcript_path"])

    # If this is an Agent tool call, record it so SubagentStart can find it
    if tool_name == "Agent":
        _pending_agent_tools[tool_use_id] = tool_input

    try:
        # Determine parent: subagent chain > root chain.
        # Tool runs are siblings of LLM runs, not children.
        parent: Optional[RunTree] = None
        if agent_id and agent_id in _subagent_runs:
            parent = _subagent_runs[agent_id]
        else:
            parent = get_parent_run_tree() or get_current_run_tree()

        if not parent:
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
        input_data: Contains `tool_name`, `tool_input`, `tool_response`,
            `session_id`, etc.
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context (currently contains only signal)

    Returns:
        Hook output (empty `dict` by default)
    """
    if not tool_use_id:
        return {}

    tool_name: str = str(input_data.get("tool_name", "unknown_tool"))
    tool_response = input_data.get("tool_response")

    try:
        run_info = _active_tool_runs.pop(tool_use_id, None)
        if not run_info:
            return {}

        tool_run, _ = run_info

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

        tool_run.end(
            outputs=outputs,
            error=outputs.get("output") if is_error else None,
        )

        try:
            tool_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch tool run for {tool_name}: {e}")

        # If this is an Agent tool, also set outputs on the stashed
        # subagent run.  We don't end/patch the subagent here because
        # its AssistantMessages may not have been yielded to
        # receive_response() yet.  clear_active_tool_runs() will
        # finalise it at the end of the conversation.
        subagent_run = _ended_subagent_runs.get(tool_use_id)
        if subagent_run:
            try:
                subagent_run.outputs = outputs
            except Exception as e:
                logger.warning(f"Failed to set subagent run outputs: {e}")

    except Exception as e:
        logger.warning(
            f"Error in PostToolUse hook for {tool_name}: {e}",
            exc_info=True,
        )

    return {}


async def post_tool_use_failure_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Trace tool execution when it fails.

    This hook fires for built-in tool failures (Bash, Read, Write, etc.)
    and is mutually exclusive with :func:`post_tool_use_hook` — when a
    built-in tool fails, only ``PostToolUseFailure`` fires.

    Args:
        input_data: Contains ``tool_name``, ``tool_input``, ``error``,
            and optionally ``is_interrupt``.
        tool_use_id: Unique identifier for this tool invocation
        context: Hook context (currently contains only signal)

    Returns:
        Hook output (empty dict)
    """
    if not tool_use_id:
        return {}

    tool_name: str = str(input_data.get("tool_name", "unknown_tool"))
    error: str = str(input_data.get("error", "Unknown error"))

    try:
        run_info = _active_tool_runs.pop(tool_use_id, None)
        if not run_info:
            return {}

        tool_run, _ = run_info

        tool_run.end(
            outputs={"error": error},
            error=error,
        )

        try:
            tool_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch failed tool run for {tool_name}: {e}")

    except Exception as e:
        logger.warning(
            f"Error in PostToolUseFailure hook for {tool_name}: {e}",
            exc_info=True,
        )

    return {}


async def subagent_start_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Create a chain run when a subagent starts.

    The subagent chain is nested under the Agent tool run that spawned it.
    Since the SDK passes a different ``tool_use_id`` to this hook than the
    one from ``PreToolUse`` for the Agent tool, we match them via the
    ``_pending_agent_tools`` queue.

    Args:
        input_data: Contains ``agent_id``, ``agent_type``, ``session_id``
        tool_use_id: SDK-internal session id (not the Agent tool's
            tool_use_id)
        context: Hook context

    Returns:
        Hook output (empty dict)
    """
    data: dict[str, Any] = dict(input_data)
    agent_id: Optional[str] = str(data["agent_id"]) if data.get("agent_id") else None
    agent_type: str = str(data.get("agent_type") or "subagent")

    if not agent_id:
        return {}

    try:
        # Find the Agent tool run that triggered this subagent.
        # _pending_agent_tools is populated by pre_tool_use_hook when
        # tool_name == "Agent".  Pop the most recent one.
        agent_tool_use_id: Optional[str] = None
        agent_tool_input: dict[str, Any] = {}
        parent: Optional[RunTree] = None

        if _pending_agent_tools:
            agent_tool_use_id, agent_tool_input = _pending_agent_tools.popitem()

            if agent_tool_use_id in _active_tool_runs:
                agent_tool_run, _ = _active_tool_runs[agent_tool_use_id]
                parent = agent_tool_run

        if parent is None:
            parent = get_parent_run_tree() or get_current_run_tree()

        if not parent:
            return {}

        start_time = time.time()
        subagent_run = parent.create_child(
            name=agent_type,
            run_type="chain",
            inputs=agent_tool_input if agent_tool_input else {},
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )
        subagent_run.extra["metadata"] = {
            **subagent_run.extra.get("metadata", {}),
            "ls_agent_type": "subagent",
        }

        try:
            subagent_run.post()
        except Exception as e:
            logger.warning(f"Failed to post subagent run: {e}")

        # Store by agent_id so tool hooks and LLM run lookup can find it
        _subagent_runs[agent_id] = subagent_run

        # Remember which Agent tool_use_id spawned this agent_id
        if agent_tool_use_id:
            _agent_to_tool_mapping[agent_id] = agent_tool_use_id

    except Exception as e:
        logger.warning(f"Error in SubagentStart hook: {e}", exc_info=True)

    return {}


async def subagent_stop_hook(
    input_data: "HookInput",
    tool_use_id: Optional[str],
    context: "HookContext",
) -> "HookJSONOutput":
    """Move the subagent run to ended state when it finishes.

    Does NOT end/patch the run — ``PostToolUse`` for the Agent tool will
    set outputs, and ``clear_active_tool_runs()`` will finalise it at the
    end of the conversation.

    Args:
        input_data: Contains ``agent_id``, ``agent_type``, ``session_id``,
            ``agent_transcript_path``
        tool_use_id: SDK-internal session id
        context: Hook context

    Returns:
        Hook output (empty dict)
    """
    data: dict[str, Any] = dict(input_data)
    agent_id: Optional[str] = str(data["agent_id"]) if data.get("agent_id") else None
    transcript_path: Optional[str] = (
        str(data["agent_transcript_path"])
        if data.get("agent_transcript_path")
        else None
    )

    if not agent_id:
        return {}

    try:
        subagent_run = _subagent_runs.pop(agent_id, None)
        if not subagent_run:
            return {}

        if transcript_path:
            _subagent_transcript_paths.append((transcript_path, subagent_run))

        # Move to ended state so PostToolUse can set outputs.
        agent_tool_id = _agent_to_tool_mapping.pop(agent_id, None)
        if agent_tool_id:
            _ended_subagent_runs[agent_tool_id] = subagent_run
        else:
            # No matching Agent tool — just end it now
            subagent_run.end()
            try:
                subagent_run.patch()
            except Exception as e:
                logger.warning(f"Failed to patch subagent run: {e}")

    except Exception as e:
        logger.warning(f"Error in SubagentStop hook: {e}", exc_info=True)

    return {}


# ── Cleanup ───────────────────────────────────────────────────────────────────


def clear_active_tool_runs() -> None:
    """Finalise all runs and clear module state.

    Called by ``receive_response()`` when a conversation ends.
    """
    # 1. End orphaned subagent runs (SubagentStop never fired)
    for agent_id, subagent_run in _subagent_runs.items():
        try:
            subagent_run.end(error="Subagent run not completed (conversation ended)")
            subagent_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned subagent run {agent_id}: {e}")

    # 2. Finalise ended subagent runs (outputs already set by PostToolUse)
    for tool_use_id, subagent_run in _ended_subagent_runs.items():
        try:
            subagent_run.end()
            subagent_run.patch()
        except Exception as e:
            logger.debug(f"Failed to finalise ended subagent run {tool_use_id}: {e}")

    # 3. End orphaned tool runs
    for tool_use_id, (tool_run, _) in _active_tool_runs.items():
        try:
            tool_run.end(error="Tool run not completed (conversation ended)")
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned tool run {tool_use_id}: {e}")

    # 4. Reset all state
    global _main_transcript_path
    _active_tool_runs.clear()
    _subagent_runs.clear()
    _pending_agent_tools.clear()
    _agent_to_tool_mapping.clear()
    _ended_subagent_runs.clear()
    _subagent_transcript_paths.clear()
    _main_transcript_path = None
