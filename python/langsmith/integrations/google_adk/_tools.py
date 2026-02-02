"""Context variable storage for parent run tree."""

from __future__ import annotations

import contextvars
from typing import Any

_parent_run_tree: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "langsmith_adk_parent_run_tree", default=None
)


def set_parent_run_tree(run_tree: Any) -> contextvars.Token[Any]:
    """Set the parent run tree and return a token for reset."""
    return _parent_run_tree.set(run_tree)


def clear_parent_run_tree(token: contextvars.Token[Any] | None = None) -> None:
    """Clear the parent run tree context."""
    if token is not None:
        _parent_run_tree.reset(token)
    else:
        _parent_run_tree.set(None)


def get_parent_run_tree() -> Any:
    """Get the parent run tree from context."""
    return _parent_run_tree.get()
