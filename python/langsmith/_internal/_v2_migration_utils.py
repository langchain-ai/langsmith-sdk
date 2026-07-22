"""Utilities for migrating functionality to the v2 LangSmith API."""

from __future__ import annotations

import datetime
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
