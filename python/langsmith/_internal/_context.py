"""Shared context (ContextVars and global defaults) that configure tracing."""

import contextvars
import weakref
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

if TYPE_CHECKING:
    from langsmith.client import Client
    from langsmith.run_trees import RunTree
else:
    Client = Any  # type: ignore[assignment]
    RunTree = Any  # type: ignore[assignment]

_PROJECT_NAME = contextvars.ContextVar[Optional[str]]("_PROJECT_NAME", default=None)
_TAGS = contextvars.ContextVar[Optional[list[str]]]("_TAGS", default=None)
_METADATA = contextvars.ContextVar[Optional[dict[str, Any]]]("_METADATA", default=None)

_TRACING_ENABLED = contextvars.ContextVar[Optional[Union[bool, Literal["local"]]]](
    "_TRACING_ENABLED", default=None
)
_CLIENT = contextvars.ContextVar[Optional["Client"]]("_CLIENT", default=None)

# Store only the RunTree ID (string) in the context.
# The actual RunTree is stored in a WeakValueDictionary, allowing it to be
# garbage collected when no strong references exist. This prevents memory leaks
# when contexts are captured by asyncio operations.
_PARENT_RUN_TREE_ID = contextvars.ContextVar[Optional[str]](
    "_PARENT_RUN_TREE_ID", default=None
)

# WeakValueDictionary mapping RunTree ID -> RunTree.
# Uses weak references so RunTrees can be garbage collected when no longer needed.
_RUN_TREE_REGISTRY: weakref.WeakValueDictionary[str, "RunTree"] = (
    weakref.WeakValueDictionary()
)


def register_run_tree(run: "RunTree") -> str:
    """Register a RunTree in the registry and return its ID.

    The RunTree is stored with a weak reference, allowing it to be garbage
    collected when no strong references exist (e.g., after a traceable function
    completes and its run_container goes out of scope).

    Args:
        run: The RunTree to register.

    Returns:
        The RunTree's ID as a string.
    """
    run_id = str(run.id)
    _RUN_TREE_REGISTRY[run_id] = run
    return run_id


def get_run_tree_by_id(run_id: Optional[str]) -> Optional["RunTree"]:
    """Get a RunTree by its ID from the registry.

    Args:
        run_id: The RunTree ID, or None.

    Returns:
        The RunTree if found and still alive, otherwise None.
    """
    if run_id is None:
        return None
    return _RUN_TREE_REGISTRY.get(run_id)


def get_current_run_tree_id() -> Optional[str]:
    """Get the current RunTree ID from the context.

    Returns:
        The current RunTree ID, or None if not set.
    """
    return _PARENT_RUN_TREE_ID.get()


# Not thread-local, so you can set this process-wide (before asyncio.run, etc.)
_GLOBAL_PROJECT_NAME: Optional[str] = None
_GLOBAL_TAGS: Optional[list[str]] = None
_GLOBAL_METADATA: Optional[dict[str, Any]] = None
_GLOBAL_TRACING_ENABLED: Optional[Union[bool, Literal["local"]]] = None
_GLOBAL_CLIENT: Optional["Client"] = None
