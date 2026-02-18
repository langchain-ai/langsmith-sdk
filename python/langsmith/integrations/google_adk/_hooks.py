"""Callback-based tracing for Google ADK agents and tools."""

from __future__ import annotations

import logging
import threading
import time
from contextvars import Token
from datetime import datetime, timezone
from typing import Any, Optional

from langsmith._internal import _context
from langsmith.run_helpers import get_current_run_tree
from langsmith.run_trees import RunTree

logger = logging.getLogger(__name__)

_active_agent_runs: dict[
    str, list[tuple[RunTree, float, Token[Optional[RunTree]]]]
] = {}
_active_tool_runs: dict[str, list[tuple[RunTree, float]]] = {}
_sync_root_runs: dict[tuple[str, str, str], list[RunTree]] = {}
_sync_root_runs_lock = threading.Lock()


def _get_session_key(
    *,
    app_name: Any = None,
    user_id: Any = None,
    session_id: Any = None,
) -> Optional[tuple[str, str, str]]:
    if app_name is None or user_id is None or session_id is None:
        return None
    return (str(app_name), str(user_id), str(session_id))


def register_sync_root_run(
    *, app_name: Any, user_id: Any, session_id: Any, run: RunTree
) -> None:
    """Register root span for sync Runner.run execution across thread boundary."""
    session_key = _get_session_key(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if session_key is None:
        return
    with _sync_root_runs_lock:
        _sync_root_runs.setdefault(session_key, []).append(run)


def unregister_sync_root_run(
    *, app_name: Any, user_id: Any, session_id: Any, run: RunTree
) -> None:
    """Remove previously registered root span for sync Runner.run."""
    session_key = _get_session_key(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if session_key is None:
        return
    with _sync_root_runs_lock:
        run_stack = _sync_root_runs.get(session_key)
        if not run_stack:
            return
        for idx in range(len(run_stack) - 1, -1, -1):
            if run_stack[idx] is run:
                run_stack.pop(idx)
                break
        if not run_stack:
            _sync_root_runs.pop(session_key, None)


def get_sync_root_run(
    *, app_name: Any = None, user_id: Any = None, session_id: Any = None
) -> Optional[RunTree]:
    """Get active sync root span for a session, if one is registered."""
    session_key = _get_session_key(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if session_key is None:
        return None
    with _sync_root_runs_lock:
        run_stack = _sync_root_runs.get(session_key)
        if not run_stack:
            return None
        return run_stack[-1]


def _extract_session_identifiers(context: Any) -> tuple[Any, Any, Any]:
    session = getattr(context, "session", None)
    app_name = getattr(session, "app_name", None)
    user_id = getattr(context, "user_id", None) or getattr(session, "user_id", None)
    session_id = getattr(session, "id", None)
    return app_name, user_id, session_id


def _extract_text_from_content(content: Any) -> Optional[str]:
    parts = getattr(content, "parts", None) or []
    text_parts = [str(part.text) for part in parts if getattr(part, "text", None)]
    if not text_parts:
        return None
    return " ".join(text_parts)


def _iter_invocation_events(callback_context: Any) -> list[Any]:
    session = getattr(callback_context, "session", None)
    if session is None:
        return []
    invocation_id = getattr(callback_context, "invocation_id", None)
    events = getattr(session, "events", None) or []
    if invocation_id is None:
        return list(events)
    return [
        event
        for event in events
        if getattr(event, "invocation_id", None) == invocation_id
    ]


def _extract_latest_invocation_text(callback_context: Any) -> Optional[str]:
    for event in reversed(_iter_invocation_events(callback_context)):
        text = _extract_text_from_content(getattr(event, "content", None))
        if text:
            return text
    return None


def _extract_latest_agent_text(callback_context: Any) -> Optional[str]:
    agent_name = getattr(callback_context, "agent_name", None)
    if agent_name is None:
        return None
    for event in reversed(_iter_invocation_events(callback_context)):
        if getattr(event, "author", None) != agent_name:
            continue
        text = _extract_text_from_content(getattr(event, "content", None))
        if text:
            return text
    return None


def _get_parent_run(
    *,
    app_name: Any = None,
    user_id: Any = None,
    session_id: Any = None,
) -> Optional[RunTree]:
    parent = get_current_run_tree()
    if parent is not None:
        return parent
    return get_sync_root_run(app_name=app_name, user_id=user_id, session_id=session_id)


def before_agent_callback(callback_context: Any, *args: Any, **kwargs: Any) -> None:
    """Create chain run for agent invocation."""
    invocation_id = getattr(callback_context, "invocation_id", None)
    if not invocation_id:
        return

    agent_name = getattr(callback_context, "agent_name", None) or "google_adk_agent"
    app_name, user_id, session_id = _extract_session_identifiers(callback_context)

    parent = _get_parent_run(app_name=app_name, user_id=user_id, session_id=session_id)
    if not parent:
        return

    try:
        start_time = time.time()
        inputs: dict[str, Any] = {}

        latest_input = _extract_latest_invocation_text(callback_context)
        if latest_input:
            inputs["input"] = latest_input
        elif user_content := getattr(callback_context, "user_content", None):
            if text := _extract_text_from_content(user_content):
                inputs["input"] = text

        agent_run = parent.create_child(
            name=agent_name,
            run_type="chain",
            inputs=inputs,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )
        agent_run.post()

        # Set agent span as current parent for nested operations
        token = _context._PARENT_RUN_TREE.set(agent_run)

        # Store agent span with token for restoration
        _active_agent_runs.setdefault(invocation_id, []).append(
            (agent_run, start_time, token)
        )
    except Exception as e:
        logger.warning(f"Error in before_agent_callback: {e}")


def after_agent_callback(callback_context: Any, *args: Any, **kwargs: Any) -> None:
    """End agent run with final output."""
    invocation_id = getattr(callback_context, "invocation_id", None)
    if not invocation_id:
        return

    run_stack = _active_agent_runs.get(invocation_id)
    if not run_stack:
        return

    agent_run, _, token = run_stack.pop()
    if not run_stack:
        _active_agent_runs.pop(invocation_id, None)

    try:
        outputs: dict[str, Any] = {}
        if text := _extract_latest_agent_text(callback_context):
            outputs["output"] = text

        agent_run.end(outputs=outputs if outputs else None)
        agent_run.patch()
    except Exception as e:
        logger.warning(f"Error in after_agent_callback: {e}")
    finally:
        # Always restore context, even if patching fails
        _context._PARENT_RUN_TREE.reset(token)


def before_tool_callback(
    tool: Any, args: dict[str, Any], tool_context: Any, *other_args: Any, **kwargs: Any
) -> None:
    """Create tool run before execution."""
    function_call_id = (
        getattr(tool_context, "function_call_id", None)
        or f"tool_{id(tool)}_{id(tool_context)}"
    )
    tool_name = getattr(tool, "name", None) or type(tool).__name__
    app_name, user_id, session_id = _extract_session_identifiers(tool_context)
    parent = _get_parent_run(app_name=app_name, user_id=user_id, session_id=session_id)
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
        _active_tool_runs.setdefault(function_call_id, []).append(
            (tool_run, start_time)
        )
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
    run_stack = _active_tool_runs.get(function_call_id)
    if not run_stack:
        return

    try:
        tool_run, _ = run_stack.pop()
        if not run_stack:
            _active_tool_runs.pop(function_call_id, None)

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

    for run_infos in _active_agent_runs.values():
        for run, _, token in run_infos:
            try:
                run.end(error="Session ended")
                run.patch()
            except Exception:
                pass
            finally:
                try:
                    _context._PARENT_RUN_TREE.reset(token)
                except Exception:
                    pass

    for tool_run_infos in _active_tool_runs.values():
        for run, _ in tool_run_infos:
            try:
                run.end(error="Session ended")
                run.patch()
            except Exception:
                pass

    _active_agent_runs.clear()
    _active_tool_runs.clear()
