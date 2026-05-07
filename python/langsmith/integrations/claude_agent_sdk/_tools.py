"""Context-var storage utilities for Claude Agent SDK tracing.

This module stores the *parent run tree* — the root chain span opened by
``_traced_receive_response`` — for direct/default-session hook calls. Real
instrumented client sessions primarily parent hook spans via
``SessionState.root_run``.

A :class:`contextvars.ContextVar` is used so concurrent conversations on the
same thread (e.g. multiple ``ClaudeSDKClient`` instances driven by
``asyncio.gather``) each see their own parent run tree.
"""

from contextvars import ContextVar
from typing import Any, Optional

_parent_run_tree: ContextVar[Optional[Any]] = ContextVar(
    "langsmith_claude_agent_parent_run_tree", default=None
)


def set_parent_run_tree(run_tree: Any) -> Any:
    """Bind *run_tree* to the current context and return a reset token."""
    return _parent_run_tree.set(run_tree)


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


def get_parent_run_tree() -> Any:
    """Return the parent run tree bound to the current context."""
    return _parent_run_tree.get()
