"""Metadata for traced sandbox operations."""

from typing import Optional


def add_sandbox_metadata(sandbox_id: Optional[str]) -> None:
    """Associate the active run with a known sandbox ID without creating a run."""
    if not sandbox_id:
        return
    from langsmith.run_helpers import get_current_run_tree

    run = get_current_run_tree()
    if run is not None:
        run.add_metadata({"sandbox_id": sandbox_id})
