"""Context-var storage utilities for Claude Agent SDK tracing.

This module stores the *parent run tree* — the root chain span opened by
``_traced_receive_response`` — so that hook functions can nest tool and
subagent runs underneath it.

A :class:`contextvars.ContextVar` is used rather than thread-local storage
so that concurrent conversations on the *same thread* (e.g. multiple
``ClaudeSDKClient`` instances driven by ``asyncio.gather``) each see their
own parent run tree. ContextVar values are copied across ``asyncio.Task``
boundaries automatically, which matches how the Claude Agent SDK schedules
hook callbacks.

A thread-local mirror is also maintained as a fallback for the rare cases
where a hook runs on a fresh worker thread that did not inherit the
ContextVar — the mirror is only consulted when the ContextVar is unset.
"""

import threading
from contextvars import ContextVar
from typing import Any, Optional

# Primary storage: context-var. Propagates across asyncio tasks.
_parent_run_tree: ContextVar[Optional[Any]] = ContextVar(
    "langsmith_claude_agent_parent_run_tree", default=None
)

# Secondary fallback: thread-local. Only used when the context-var is unset
# on the current frame (e.g. hook invoked from a detached worker thread
# that did not copy the context). Because it is per-thread, it cannot
# isolate concurrent conversations running on the *same* thread — callers
# relying on it must serialise their work.
_thread_local = threading.local()


def set_parent_run_tree(run_tree: Any) -> Any:
    """Bind *run_tree* to the current context and thread-local fallback.

    Returns an opaque token that callers should pass to
    :func:`clear_parent_run_tree` when the scope ends. The token lets us
    restore the previous value rather than blowing it away, which keeps
    nested / concurrent conversations isolated.
    """
    token = _parent_run_tree.set(run_tree)
    _thread_local.parent_run_tree = run_tree
    return token


def clear_parent_run_tree(token: Any = None) -> None:
    """Reset the parent run tree in the current context.

    If a *token* from :func:`set_parent_run_tree` is provided, it is used
    to restore the previous value; otherwise the context is cleared.
    """
    if token is not None:
        try:
            _parent_run_tree.reset(token)
        except ValueError:
            _parent_run_tree.set(None)
    else:
        _parent_run_tree.set(None)
    if hasattr(_thread_local, "parent_run_tree"):
        delattr(_thread_local, "parent_run_tree")


def get_parent_run_tree() -> Any:
    """Return the parent run tree bound to the current context."""
    run_tree = _parent_run_tree.get()
    if run_tree is not None:
        return run_tree
    return getattr(_thread_local, "parent_run_tree", None)
