"""Integration tests for v2 resources exposed on Client and AsyncClient."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Generator

import pytest

from langsmith import AsyncClient, Client
from langsmith.run_trees import RunTree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SELECTS = [
    "ID",
    "NAME",
    "RUN_TYPE",
    "STATUS",
    "START_TIME",
    "END_TIME",
    "INPUTS",
    "OUTPUTS",
    "TAGS",
    "PROJECT_ID",
    "TRACE_ID",
    "DOTTED_ORDER",
]


def _create_project_name(suffix: str) -> str:
    return f"__test_v2_resources_{suffix}_{uuid.uuid4().hex}"


def _cleanup_project(client: Client, project_name: str) -> None:
    try:
        client.delete_project(project_name=project_name)
    except Exception:
        pass


def _get_project_id_or_skip(
    client: Client,
    project_name: str,
    max_retries: int = 30,
    sleep_time: float = 2.0,
) -> str:
    """Return project_id, retrying until found; skip if key lacks projects:read."""
    for _ in range(max_retries):
        try:
            project = client.read_project(project_name=project_name)
            return str(project.id)
        except Exception as e:
            msg = str(e)
            if "projects:read" in msg or "403" in msg:
                pytest.skip(
                    "requires projects:read permission (service key limitation)"
                )
        time.sleep(sleep_time)
    pytest.fail(f"Project {project_name!r} not found after {max_retries} retries")


def _post_trace(project_name: str) -> tuple[str, str, datetime]:
    """Create a trace (root run + child).

    Returns (trace_id, project_id, start_time).
    """
    client = Client()
    start = datetime.now(timezone.utc)
    root = RunTree(
        name="root_run",
        run_type="chain",
        inputs={"input": "hello"},
        project_name=project_name,
    )
    root.post()
    child = root.create_child(
        name="child_run",
        run_type="llm",
        inputs={"prompt": "world"},
    )
    child.post()
    child.end(outputs={"text": "done"})
    child.patch()
    root.end(outputs={"result": "ok"})
    root.patch()
    project_id = _get_project_id_or_skip(client, project_name)
    return str(root.id), project_id, start


# ---------------------------------------------------------------------------
# Sync Client tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_client() -> Generator[Client, None, None]:
    yield Client()


def test_runs_retrieve(sync_client: Client) -> None:
    project_name = _create_project_name("runs_retrieve")
    run_id, project_id, start = _post_trace(project_name)

    run = sync_client.runs.retrieve(
        run_id=run_id,
        project_id=project_id,
        start_time=start.isoformat(),
    )
    assert run.id == run_id

    _cleanup_project(sync_client, project_name)


def test_runs_query(sync_client: Client) -> None:
    project_name = _create_project_name("runs_query")
    trace_id, project_id, _ = _post_trace(project_name)

    runs = list(
        sync_client.runs.query(
            project_ids=[project_id],
            selects=DEFAULT_SELECTS,
        )
    )
    assert len(runs) >= 1
    trace_ids = {r.trace_id for r in runs}
    assert trace_id in trace_ids

    _cleanup_project(sync_client, project_name)



# ---------------------------------------------------------------------------
# Async Client tests
# ---------------------------------------------------------------------------


@pytest.fixture
def async_client() -> AsyncClient:
    return AsyncClient()


@pytest.mark.asyncio
async def test_async_runs_retrieve(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_runs_retrieve")
    run_id, project_id, start = _post_trace(project_name)

    run = await async_client.runs.retrieve(
        run_id=run_id,
        project_id=project_id,
        start_time=start.isoformat(),
    )
    assert run.id == run_id

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_runs_query(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_runs_query")
    trace_id, project_id, _ = _post_trace(project_name)

    runs = []
    async for run in async_client.runs.query(
        project_ids=[project_id],
        selects=DEFAULT_SELECTS,
    ):
        runs.append(run)

    assert len(runs) >= 1
    trace_ids = {r.trace_id for r in runs}
    assert trace_id in trace_ids

    _cleanup_project(sync, project_name)





