"""Hook-based tool tracing for Claude Agent SDK.

Correlation state is scoped **per-session** via a :class:`contextvars.ContextVar`.
Each ``receive_response()`` call opens a fresh :class:`SessionState` and binds
it to the context var so that hook functions — which run on the SDK's async
event loop — look up the correct session's state regardless of how many
``ClaudeSDKClient`` instances are concurrently active in the process.

Hooks fire in one of three contexts:

1. Inside the ``async with trace(...)`` block of ``_traced_receive_response``.
   The ContextVar is set; state is read/written on the per-session instance.
2. In a hook task spawned by the SDK on the *same* event loop — ``ContextVar``
   values are copied into child tasks, so isolation still holds.
3. In a detached worker where the ContextVar is unset (rare). A secondary
   registry keyed by ``session_id`` (taken from ``BaseHookInput``) allows
   hooks to still find the right session.

For backward compatibility with code and tests that touch module-level names
(``_active_tool_runs``, ``_main_transcript_path``, etc.), those names continue
to refer to a module-level *default* session which is used when no ContextVar
is active. Real concurrent traffic under ``receive_response`` never hits the
default session.
"""

import logging
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
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


# ── Per-session state ─────────────────────────────────────────────────────────


@dataclass
class SessionState:
    """All mutable correlation state for a single conversation.

    One instance is created per ``receive_response()`` call and bound to the
    ``_current_session`` ContextVar for the duration of that call.
    """

    # Key: tool_use_id → (run_tree, start_time)
    active_tool_runs: dict[str, tuple[Any, float]] = field(default_factory=dict)

    # Key: agent_id → RunTree for the subagent chain.
    # Populated by SubagentStart, consumed by SubagentStop.
    subagent_runs: dict[str, RunTree] = field(default_factory=dict)

    # Key: tool_use_id → tool_input dict.
    # When PreToolUse fires for an "Agent" tool, it stashes here.
    # SubagentStart pops it to find the matching Agent tool run.
    pending_agent_tools: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Key: agent_id → Agent tool_use_id.
    # Maps a subagent back to the Agent tool that spawned it.
    agent_to_tool_mapping: dict[str, str] = field(default_factory=dict)

    # Key: Agent tool_use_id → RunTree.
    # SubagentStop moves the run here; PostToolUse sets outputs on it;
    # clear_active_tool_runs() ends + patches it.
    ended_subagent_runs: dict[str, RunTree] = field(default_factory=dict)

    # (transcript_path, subagent_RunTree) captured from SubagentStop.
    # Used for usage extraction and creating missing LLM runs.
    subagent_transcript_paths: list[tuple[str, RunTree]] = field(default_factory=list)

    # Main session transcript path, captured from BaseHookInput.transcript_path
    # on the first hook that fires (every hook inherits this field).
    main_transcript_path: Optional[str] = None

    # Claude SDK session ids (for fallback lookup when ContextVar is unset).
    session_ids: set[str] = field(default_factory=set)

    # Root LangSmith run id (for fallback lookup when ContextVar is unset and
    # the SDK did not include a Claude session_id on the hook input).
    root_run_id: Optional[str] = None

    @property
    def session_id(self) -> Optional[str]:
        """Backward-compatible first session id, if any."""
        return next(iter(self.session_ids), None)

    @session_id.setter
    def session_id(self, value: Optional[str]) -> None:
        if value:
            self.session_ids.add(value)
        else:
            self.session_ids.clear()


# Module-level *default* session. Used when no ContextVar is set (e.g. tests
# that poke hooks directly, or hooks firing outside a traced conversation).
# Also serves as the backing store for the legacy module-level attribute
# names exposed below.
_default_session: SessionState = SessionState()

# ContextVar holding the active session for a conversation. When set, hooks
# use this session; otherwise they fall back to the session registry
# (``_sessions_by_id``) or finally the default session.
_current_session: ContextVar[Optional[SessionState]] = ContextVar(
    "langsmith_claude_agent_session", default=None
)

# Fallback registries used when a hook fires on a task/thread where the
# ContextVar was not propagated. Protected by ``_sessions_lock`` because
# registration/lookup can race across threads.
_sessions_by_id: dict[str, SessionState] = {}
_sessions_by_root_run_id: dict[str, SessionState] = {}
_sessions_lock = threading.Lock()


def _current_session_or_default() -> SessionState:
    """Return the best session for the current execution context."""
    session = _current_session.get()
    if session is not None:
        return session
    parent = get_parent_run_tree()
    parent_id = getattr(parent, "id", None)
    if parent_id is not None:
        with _sessions_lock:
            session = _sessions_by_root_run_id.get(str(parent_id))
        if session is not None:
            return session
    return _default_session


def _session_for_hook(data: dict[str, Any]) -> SessionState:
    """Resolve the session that owns the current hook invocation.

    Preference order:

    1. Session bound to the current ContextVar.
    2. Session previously registered under the hook's ``session_id``.
    3. The module-level default session (last resort; only safe when no
       concurrent conversation is in flight).
    """
    session = _current_session.get()
    if session is not None:
        # Lazily remember this session_id → session mapping so tasks that
        # lose the ContextVar can still find the right session.
        sid = data.get("session_id")
        if sid:
            sid = str(sid)
            session.session_ids.add(sid)
            with _sessions_lock:
                _sessions_by_id[sid] = session
        return session

    sid = data.get("session_id")
    if sid:
        with _sessions_lock:
            existing = _sessions_by_id.get(str(sid))
        if existing is not None:
            return existing

    parent = get_parent_run_tree()
    parent_id = getattr(parent, "id", None)
    if parent_id is not None:
        with _sessions_lock:
            existing = _sessions_by_root_run_id.get(str(parent_id))
        if existing is not None:
            return existing

    return _default_session


def _register_session(session: SessionState) -> object:
    """Bind *session* to the ContextVar and return a reset token.

    The caller must pass the returned token to ``_unregister_session`` when
    the conversation ends.
    """
    return _current_session.set(session)


def _set_session_root(session: SessionState, run_tree: RunTree) -> None:
    """Register *session* under its root LangSmith run id."""
    root_run_id = str(run_tree.id)
    session.root_run_id = root_run_id
    with _sessions_lock:
        _sessions_by_root_run_id[root_run_id] = session


def _unregister_session(session: SessionState, token: Any) -> None:
    """Reset the ContextVar and deregister the session from fallback registries."""
    try:
        _current_session.reset(token)
    except ValueError:
        # Token was created in a different context — fall back to clearing.
        _current_session.set(None)

    with _sessions_lock:
        for sid, value in list(_sessions_by_id.items()):
            if value is session:
                _sessions_by_id.pop(sid, None)
        for root_run_id, value in list(_sessions_by_root_run_id.items()):
            if value is session:
                _sessions_by_root_run_id.pop(root_run_id, None)


# ── Legacy module-level attribute shims ───────────────────────────────────────
# These names are part of the historical public surface of this module
# (tests import them directly). They now alias the *default* session's
# fields. Real concurrent usage operates on per-session instances and is
# unaffected by reads/writes here.

_active_tool_runs = _default_session.active_tool_runs
_subagent_runs = _default_session.subagent_runs
_pending_agent_tools = _default_session.pending_agent_tools
_agent_to_tool_mapping = _default_session.agent_to_tool_mapping
_ended_subagent_runs = _default_session.ended_subagent_runs
_subagent_transcript_paths = _default_session.subagent_transcript_paths

# Mirrored from ``_default_session.main_transcript_path``. Kept in sync by
# hook functions that operate on the default session, and by
# ``clear_active_tool_runs``.
_main_transcript_path: Optional[str] = None


# ── Public helpers (used by _client.py) ───────────────────────────────────────


def get_subagent_run_by_tool_id(tool_use_id: str) -> Optional[RunTree]:
    """Get a subagent run by the Agent tool's tool_use_id.

    Checks both active subagent runs and ended-but-not-finalised runs,
    because the SDK fires ``SubagentStop`` before the subagent's messages
    reach the client.
    """
    session = _current_session_or_default()
    # Check active subagents first
    for aid, tid in session.agent_to_tool_mapping.items():
        if tid == tool_use_id:
            return session.subagent_runs.get(aid)
    # Fall back to ended-but-not-finalised subagents
    return session.ended_subagent_runs.get(tool_use_id)


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

    data: dict[str, Any] = dict(input_data)  # flatten TypedDict union
    tool_name: str = str(data.get("tool_name", "unknown_tool"))
    tool_input: dict[str, Any] = dict(data.get("tool_input") or {})
    agent_id: Optional[str] = str(data["agent_id"]) if data.get("agent_id") else None
    session = _session_for_hook(data)

    # Capture main session transcript path from BaseHookInput
    if session.main_transcript_path is None and data.get("transcript_path"):
        session.main_transcript_path = str(data["transcript_path"])
        if session is _default_session:
            global _main_transcript_path
            _main_transcript_path = session.main_transcript_path

    # If this is an Agent tool call, record it so SubagentStart can find it
    if tool_name == "Agent":
        session.pending_agent_tools[tool_use_id] = tool_input

    try:
        # Determine parent: subagent chain > root chain.
        # Tool runs are siblings of LLM runs, not children.
        parent: Optional[RunTree] = None
        if agent_id and agent_id in session.subagent_runs:
            parent = session.subagent_runs[agent_id]
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

        session.active_tool_runs[tool_use_id] = (tool_run, start_time)

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
    session = _session_for_hook(dict(input_data))

    try:
        run_info = session.active_tool_runs.pop(tool_use_id, None)
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
        subagent_run = session.ended_subagent_runs.get(tool_use_id)
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
    session = _session_for_hook(dict(input_data))

    try:
        run_info = session.active_tool_runs.pop(tool_use_id, None)
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
    session = _session_for_hook(data)

    if not agent_id:
        return {}

    try:
        # Find the Agent tool run that triggered this subagent.
        # pending_agent_tools is populated by pre_tool_use_hook when
        # tool_name == "Agent".  Pop the most recent one.
        agent_tool_use_id: Optional[str] = None
        agent_tool_input: dict[str, Any] = {}
        parent: Optional[RunTree] = None

        if session.pending_agent_tools:
            agent_tool_use_id, agent_tool_input = session.pending_agent_tools.popitem()

            if agent_tool_use_id in session.active_tool_runs:
                agent_tool_run, _ = session.active_tool_runs[agent_tool_use_id]
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
        session.subagent_runs[agent_id] = subagent_run

        # Remember which Agent tool_use_id spawned this agent_id
        if agent_tool_use_id:
            session.agent_to_tool_mapping[agent_id] = agent_tool_use_id

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
    session = _session_for_hook(data)

    if not agent_id:
        return {}

    try:
        subagent_run = session.subagent_runs.pop(agent_id, None)
        if not subagent_run:
            return {}

        if transcript_path:
            session.subagent_transcript_paths.append((transcript_path, subagent_run))

        # Move to ended state so PostToolUse can set outputs.
        agent_tool_id = session.agent_to_tool_mapping.pop(agent_id, None)
        if agent_tool_id:
            session.ended_subagent_runs[agent_tool_id] = subagent_run
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


def clear_active_tool_runs(session: Optional[SessionState] = None) -> None:
    """Finalise all runs and clear state for *session*.

    If *session* is omitted the current ContextVar-bound session is used
    (falling back to the module-level default session). ``receive_response``
    passes the per-call session explicitly.
    """
    if session is None:
        session = _current_session_or_default()

    # 1. End orphaned subagent runs (SubagentStop never fired)
    for agent_id, subagent_run in session.subagent_runs.items():
        try:
            subagent_run.end(error="Subagent run not completed (conversation ended)")
            subagent_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned subagent run {agent_id}: {e}")

    # 2. Finalise ended subagent runs (outputs already set by PostToolUse)
    for tool_use_id, subagent_run in session.ended_subagent_runs.items():
        try:
            subagent_run.end()
            subagent_run.patch()
        except Exception as e:
            logger.debug(f"Failed to finalise ended subagent run {tool_use_id}: {e}")

    # 3. End orphaned tool runs
    for tool_use_id, (tool_run, _) in session.active_tool_runs.items():
        try:
            tool_run.end(error="Tool run not completed (conversation ended)")
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned tool run {tool_use_id}: {e}")

    # 4. Reset session state
    session.active_tool_runs.clear()
    session.subagent_runs.clear()
    session.pending_agent_tools.clear()
    session.agent_to_tool_mapping.clear()
    session.ended_subagent_runs.clear()
    session.subagent_transcript_paths.clear()
    session.main_transcript_path = None

    if session is _default_session:
        # Keep the legacy module-level mirror in sync.
        global _main_transcript_path
        _main_transcript_path = None
