"""Utilities for migrating functionality to the v2 LangSmith API."""

from __future__ import annotations

import collections
import datetime
import uuid
from typing import TYPE_CHECKING, Any, Optional

from langsmith import schemas

if TYPE_CHECKING:
    from langsmith.client import Client


# Fields for `/v2/runs/query` (RunSelectField enum); omitting selects returns only id.
_V2_RUN_SELECTS = [
    "ID",
    "NAME",
    "RUN_TYPE",
    "STATUS",
    "START_TIME",
    "END_TIME",
    "INPUTS",
    "OUTPUTS",
    "PARENT_RUN_IDS",
    "PROJECT_ID",
    "TRACE_ID",
    "DOTTED_ORDER",
    "REFERENCE_EXAMPLE_ID",
    "ERROR",
]


def _load_traces_v2(
    project: schemas.TracerSession,
    client: Client,
    *,
    is_root: Optional[bool],
) -> list[schemas.Run]:
    """List an experiment's runs from v2.

    `query_v2` defaults `min_start_time` to ~24h, so bound the window to the session
    explicitly or older experiments drop.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    kwargs: dict[str, Any] = {
        "project_ids": [str(project.id)],
        "min_start_time": project.start_time,
        "max_start_time": project.end_time or now,
        "selects": _V2_RUN_SELECTS,
    }
    if is_root is not None:
        kwargs["is_root"] = is_root
    pager = client._get_langsmith_api_sync().runs.query_v2(**kwargs)
    return [_v2_run_to_schema(run) for run in pager]


def _v2_run_to_schema(run: Any) -> schemas.Run:
    """Map a v2 `Run` to `schemas.Run`.

    `project_id`→`session_id`, `parent_run_ids[-1]`→`parent_run_id`; drop `None` so
    schema defaults apply (e.g. `dotted_order`).
    """
    parent_run_ids = getattr(run, "parent_run_ids", None)
    fields = {
        "id": run.id,
        "name": run.name,
        "run_type": run.run_type,
        "start_time": run.start_time,
        "end_time": getattr(run, "end_time", None),
        "trace_id": run.trace_id,
        "session_id": getattr(run, "project_id", None),
        "parent_run_id": parent_run_ids[-1] if parent_run_ids else None,
        "dotted_order": getattr(run, "dotted_order", None),
        "reference_example_id": getattr(run, "reference_example_id", None),
        "inputs": getattr(run, "inputs", None) or {},
        "outputs": getattr(run, "outputs", None),
        "error": getattr(run, "error", None),
        "status": (
            run.status.lower() if getattr(run, "status", None) is not None else None
        ),
    }
    return schemas.Run(
        **{key: value for key, value in fields.items() if value is not None}
    )


def _load_child_runs_v2(run: schemas.Run, client: Client) -> schemas.Run:
    """Load child runs for ``run`` using the v2 API and populate ``run.child_runs``.

    Uses ``_v2_run_to_schema`` so that returned child runs are proper
    ``schemas.Run`` objects and tree-building with ``parent_run_id`` works.
    """
    pager = client._get_langsmith_api_sync().runs.query_v2(
        project_ids=[str(run.session_id)],
        is_root=False,
        trace_id=str(run.trace_id),
        min_start_time=run.start_time,
        selects=_V2_RUN_SELECTS,
    )
    child_runs = [_v2_run_to_schema(r) for r in pager]

    treemap: collections.defaultdict[uuid.UUID, list[schemas.Run]] = (
        collections.defaultdict(list)
    )
    runs: dict[uuid.UUID, schemas.Run] = {}
    run_id_str = str(run.id)

    for child_run in sorted(child_runs, key=lambda r: r.dotted_order or ""):
        if child_run.parent_run_id is None:
            from langsmith.utils import LangSmithError

            raise LangSmithError(f"Child run {child_run.id} has no parent")
        ancestor_ids = {
            seg.split("Z", 1)[1]
            for seg in (child_run.dotted_order or "").split(".")
            if "Z" in seg
        }
        if run_id_str in ancestor_ids and str(child_run.id) != run_id_str:
            treemap[child_run.parent_run_id].append(child_run)
            runs[child_run.id] = child_run

    run.child_runs = treemap.pop(run.id, [])
    for run_id, children in treemap.items():
        if run_id in runs:
            runs[run_id].child_runs = children
    return run


def _load_nested_traces_v2(
    project_name: str, client: Client
) -> list[schemas.Run]:
    """Load all runs for ``project_name`` from the v2 API and build a trace tree.

    Equivalent to the ``_load_nested_traces`` function in ``beta/_evals.py`` but
    uses ``client.runs.query_v2`` instead of the legacy ``client.list_runs``.
    """
    project = client.read_project(project_name=project_name)
    now = datetime.datetime.now(datetime.timezone.utc)
    pager = client._get_langsmith_api_sync().runs.query_v2(
        project_ids=[str(project.id)],
        min_start_time=project.start_time,
        max_start_time=project.end_time or now,
        selects=_V2_RUN_SELECTS,
    )
    runs_flat = [_v2_run_to_schema(r) for r in pager]

    treemap: collections.defaultdict[uuid.UUID, list[schemas.Run]] = (
        collections.defaultdict(list)
    )
    results: list[schemas.Run] = []
    all_runs: dict[uuid.UUID, schemas.Run] = {}
    for run in runs_flat:
        if run.parent_run_id is not None:
            treemap[run.parent_run_id].append(run)
        else:
            results.append(run)
        all_runs[run.id] = run
    for run_id, child_runs in treemap.items():
        if run_id in all_runs:
            all_runs[run_id].child_runs = sorted(
                child_runs, key=lambda r: r.dotted_order or ""
            )
    return results
