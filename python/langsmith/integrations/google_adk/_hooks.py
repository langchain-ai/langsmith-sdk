"""Callback-based tracing for Google ADK agents and tools."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree
from langsmith.run_trees import RunTree

from ._messages import convert_adk_content_to_langsmith

logger = logging.getLogger(__name__)

_active_agent_runs: dict[str, tuple[RunTree, float]] = {}
_active_tool_runs: dict[str, tuple[RunTree, float]] = {}


def _get_parent_run() -> Optional[RunTree]:
    return get_current_run_tree()


def before_agent_callback(callback_context: Any, *args: Any, **kwargs: Any) -> None:
    """Create chain run for agent invocation."""
    invocation_id = getattr(callback_context, "invocation_id", None)
    if not invocation_id:
        return

    agent_name = getattr(callback_context, "agent_name", None) or "google_adk_agent"
    parent = _get_parent_run()
    if not parent:
        return

    try:
        start_time = time.time()
        inputs: dict[str, Any] = {}

        if user_content := getattr(callback_context, "user_content", None):
            if parts := getattr(user_content, "parts", None):
                text_parts = [str(p.text) for p in parts if getattr(p, "text", None)]
                if text_parts:
                    inputs["input"] = " ".join(text_parts)

        agent_run = parent.create_child(
            name=agent_name,
            run_type="chain",
            inputs=inputs,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )
        agent_run.post()
        _active_agent_runs[invocation_id] = (agent_run, start_time)
    except Exception as e:
        logger.warning(f"Error in before_agent_callback: {e}")


def after_agent_callback(callback_context: Any, *args: Any, **kwargs: Any) -> None:
    """End agent run with final output."""
    invocation_id = getattr(callback_context, "invocation_id", None)
    if not invocation_id:
        return

    run_info = _active_agent_runs.pop(invocation_id, None)
    if not run_info:
        return

    try:
        agent_run, _ = run_info
        outputs: dict[str, Any] = {}
        if final_response := getattr(callback_context, "final_response", None):
            outputs["output"] = convert_adk_content_to_langsmith(final_response)

        agent_run.end(outputs=outputs if outputs else None)
        agent_run.patch()
    except Exception as e:
        logger.warning(f"Error in after_agent_callback: {e}")


def before_tool_callback(
    tool: Any, args: dict[str, Any], tool_context: Any, *other_args: Any, **kwargs: Any
) -> None:
    """Create tool run before execution."""
    function_call_id = (
        getattr(tool_context, "function_call_id", None)
        or f"tool_{id(tool)}_{id(tool_context)}"
    )
    tool_name = getattr(tool, "name", None) or type(tool).__name__
    parent = _get_parent_run()
    if not parent:
        return

    try:
        start_time = time.time()
        tool_run = parent.create_child(
            name=tool_name,
            run_type="tool",
            inputs=args or {},
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )
        tool_run.post()
        _active_tool_runs[function_call_id] = (tool_run, start_time)
    except Exception as e:
        logger.warning(f"Error in before_tool_callback: {e}")


def after_tool_callback(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
    tool_response: Any,
    *other_args: Any,
    **kwargs: Any,
) -> None:
    """End tool run with response."""
    function_call_id = (
        getattr(tool_context, "function_call_id", None)
        or f"tool_{id(tool)}_{id(tool_context)}"
    )
    run_info = _active_tool_runs.pop(function_call_id, None)
    if not run_info:
        return

    try:
        tool_run, _ = run_info

        if isinstance(tool_response, dict):
            outputs = tool_response
            is_error = tool_response.get("is_error", False)
            error_msg = (
                tool_response.get("error") or tool_response.get("output")
                if is_error
                else None
            )
        elif isinstance(tool_response, list):
            outputs = {"content": tool_response}
            error_msg = None
        elif tool_response is not None:
            outputs = {"output": str(tool_response)}
            error_msg = None
        else:
            outputs = {}
            error_msg = None

        tool_run.end(outputs=outputs, error=str(error_msg) if error_msg else None)
        tool_run.patch()
    except Exception as e:
        logger.warning(f"Error in after_tool_callback: {e}")


def clear_active_runs() -> None:
    """Clear all active runs (call when session ends)."""
    global _active_agent_runs, _active_tool_runs

    for _, (run, _) in _active_agent_runs.items():
        try:
            run.end(error="Session ended")
            run.patch()
        except Exception:
            pass

    for _, (run, _) in _active_tool_runs.items():
        try:
            run.end(error="Session ended")
            run.patch()
        except Exception:
            pass

    _active_agent_runs.clear()
    _active_tool_runs.clear()
