"""Thread-local storage for parent run tree context."""

import threading
from typing import Any

_thread_local = threading.local()


def set_parent_run_tree(run_tree: Any) -> None:
    _thread_local.parent_run_tree = run_tree


def clear_parent_run_tree() -> None:
    if hasattr(_thread_local, "parent_run_tree"):
        delattr(_thread_local, "parent_run_tree")


def get_parent_run_tree() -> Any:
    return getattr(_thread_local, "parent_run_tree", None)
