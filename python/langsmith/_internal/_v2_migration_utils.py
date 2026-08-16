"""Utilities for migrating functionality to the v2 LangSmith API."""

from __future__ import annotations

import collections
import datetime
import enum
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

from langsmith import schemas
from langsmith._openapi_client._types import omit
from langsmith._openapi_client.types.run_select_field import RunSelectField

if TYPE_CHECKING:
    from langsmith.client import Client


class QueryBackend(enum.Enum):
    """Which backend(s) a LangSmith instance can serve run/trace queries from."""

    CLICKHOUSE_ONLY = "clickhouse_only"
    SMITHDB_ONLY = "smithdb_only"
    DUAL = "dual"


def get_query_backend(
    instance_flags: Optional[Mapping[str, Any]],
) -> QueryBackend:
    """Determine which backend(s) `/info`'s `instance_flags` indicate for queries.

    `ch_query_enabled` defaults to enabled when absent (older backends predate
    the flag); `sdb_query_enabled` defaults to disabled when absent.
    """
    flags = instance_flags or {}
    ch_enabled = bool(flags.get("ch_query_enabled", True))
    sdb_enabled = bool(flags.get("sdb_query_enabled", False))
    if not ch_enabled and sdb_enabled:
        return QueryBackend.SMITHDB_ONLY
    if ch_enabled and sdb_enabled:
        return QueryBackend.DUAL
    return QueryBackend.CLICKHOUSE_ONLY


# Fields for `/v2/runs/query` (RunSelectField enum); omitting selects returns only id.
_V2_RUN_SELECTS: list[RunSelectField] = [
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
    "TAGS",
    "EXTRA",
    "EVENTS",
    "FEEDBACK_STATS",
    "FIRST_TOKEN_TIME",
    "APP_PATH",
    "PROMPT_TOKENS",
    "COMPLETION_TOKENS",
    "TOTAL_TOKENS",
    "PROMPT_COST",
    "COMPLETION_COST",
    "TOTAL_COST",
    "PROMPT_TOKEN_DETAILS",
    "COMPLETION_TOKEN_DETAILS",
    "PROMPT_COST_DETAILS",
    "COMPLETION_COST_DETAILS",
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
    fb = getattr(run, "feedback_stats", None)
    events = getattr(run, "events", None)
    ptd = getattr(run, "prompt_token_details", None)
    ctd = getattr(run, "completion_token_details", None)
    pcd = getattr(run, "prompt_cost_details", None)
    ccd = getattr(run, "completion_cost_details", None)
    fields = {
        "id": run.id,
        "name": run.name,
        "run_type": run.run_type.lower() if getattr(run, "run_type", None) else None,
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
        "tags": getattr(run, "tags", None),
        "extra": getattr(run, "extra", None),
        "events": [e.model_dump() for e in events] if events else None,
        "feedback_stats": (
            {k: v.model_dump(exclude_none=True) for k, v in fb.items()} if fb else None
        ),
        "first_token_time": getattr(run, "first_token_time", None),
        "app_path": getattr(run, "app_path", None),
        "prompt_tokens": getattr(run, "prompt_tokens", None),
        "completion_tokens": getattr(run, "completion_tokens", None),
        "total_tokens": getattr(run, "total_tokens", None),
        "prompt_cost": getattr(run, "prompt_cost", None),
        "completion_cost": getattr(run, "completion_cost", None),
        "total_cost": getattr(run, "total_cost", None),
        "prompt_token_details": ptd.raw if ptd else None,
        "completion_token_details": ctd.raw if ctd else None,
        "prompt_cost_details": pcd.raw if pcd else None,
        "completion_cost_details": ccd.raw if ccd else None,
    }
    return schemas.Run(
        **{key: value for key, value in fields.items() if value is not None}
    )


def _read_run_v2(
    run_id: uuid.UUID,
    client: Client,
    *,
    project_id: uuid.UUID,
    start_time: Optional[datetime.datetime] = None,
) -> schemas.Run:
    """Fetch a single run by ID via the v2 API (for SmithDB-only backends)."""
    run = client._get_langsmith_api_sync().runs.retrieve_v2(
        run_id=str(run_id),
        project_id=str(project_id),
        selects=_V2_RUN_SELECTS,
        start_time=start_time if start_time is not None else omit,
    )
    return _v2_run_to_schema(run)


def _load_nested_traces_v2(project_name: str, client: Client) -> list[schemas.Run]:
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
