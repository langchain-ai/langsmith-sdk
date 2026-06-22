"""Integration tests for v2 OpenAPI client resources exposed on Client and AsyncClient."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Generator

import pytest

from langsmith import AsyncClient, Client
from langsmith.run_trees import RunTree, _create_current_dotted_order


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
                pytest.skip("requires projects:read permission (service key limitation)")
        time.sleep(sleep_time)
    pytest.fail(f"Project {project_name!r} not found after {max_retries} retries")


def _post_trace(project_name: str) -> tuple[str, str, datetime]:
    """Create a trace (root run + child) and return (trace_id, project_id, start_time)."""
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


def _post_thread_trace(project_name: str, thread_id: str) -> tuple[str, str, datetime]:
    """Create a run tagged with a thread_id and return (trace_id, project_id, start_time)."""
    client = Client()
    start = datetime.now(timezone.utc)
    root = RunTree(
        name="thread_root",
        run_type="chain",
        inputs={"q": "test"},
        project_name=project_name,
        extra={"metadata": {"thread_id": thread_id}},
    )
    root.post()
    root.end(outputs={"a": "answer"})
    root.patch()
    project_id = _get_project_id_or_skip(client, project_name)
    return str(root.id), project_id, start


# ---------------------------------------------------------------------------
# Sync Client tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_client() -> Generator[Client, None, None]:
    yield Client()


def test_runs_create_and_retrieve(sync_client: Client) -> None:
    project_name = _create_project_name("runs_create")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    resp = sync_client.runs.create(
        id=run_id,
        name="test_run_create",
        run_type="chain",
        inputs={"x": 1},
        start_time=now_str,
        session_name=project_name,
    )
    assert resp is not None

    project_id = _get_project_id_or_skip(sync_client, project_name)
    run = sync_client.runs.retrieve(
        run_id=run_id,
        project_id=project_id,
        start_time=now_str,
    )
    assert run.id == run_id

    _cleanup_project(sync_client, project_name)


def test_runs_update(sync_client: Client) -> None:
    project_name = _create_project_name("runs_update")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    sync_client.runs.create(
        id=run_id,
        name="update_run",
        run_type="chain",
        inputs={"x": 1},
        start_time=now,
        session_name=project_name,
    )

    resp = sync_client.runs.update(
        run_id=run_id,
        outputs={"y": 2},
        end_time=datetime.now(timezone.utc).isoformat(),
    )
    assert resp is not None

    _cleanup_project(sync_client, project_name)


def test_runs_ingest_batch(sync_client: Client) -> None:
    project_name = _create_project_name("runs_batch")
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    resp = sync_client.runs.ingest_batch(
        post=[
            {
                "id": run_id_1,
                "trace_id": run_id_1,
                "dotted_order": _create_current_dotted_order(now, uuid.UUID(run_id_1)),
                "name": "batch_run_1",
                "run_type": "chain",
                "inputs": {"n": 1},
                "start_time": now.isoformat(),
                "session_name": project_name,
            },
            {
                "id": run_id_2,
                "trace_id": run_id_2,
                "dotted_order": _create_current_dotted_order(now, uuid.UUID(run_id_2)),
                "name": "batch_run_2",
                "run_type": "llm",
                "inputs": {"n": 2},
                "start_time": now.isoformat(),
                "session_name": project_name,
            },
        ]
    )
    assert resp is not None

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


def test_runs_stats(sync_client: Client) -> None:
    project_name = _create_project_name("runs_stats")
    _, project_id, _ = _post_trace(project_name)

    stats = sync_client.runs.stats(session=[project_id])
    assert stats is not None

    _cleanup_project(sync_client, project_name)


def test_runs_update_2(sync_client: Client) -> None:
    """update_2 PATCHes a run (legacy endpoint)."""
    project_name = _create_project_name("runs_update2")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    sync_client.runs.create(
        id=run_id,
        name="update2_run",
        run_type="chain",
        inputs={"x": 1},
        start_time=now,
        session_name=project_name,
    )

    # PATCH requires at least an empty JSON body
    resp = sync_client.runs.update_2(run_id=run_id, extra_body={})
    assert resp is not None

    _cleanup_project(sync_client, project_name)


def test_threads_query(sync_client: Client) -> None:
    project_name = _create_project_name("threads_query")
    _, project_id, _ = _post_trace(project_name)

    threads = list(
        sync_client.threads.query(
            project_id=project_id,
        )
    )
    assert isinstance(threads, list)

    _cleanup_project(sync_client, project_name)


def test_threads_traces_list(sync_client: Client) -> None:
    project_name = _create_project_name("threads_traces")
    thread_id = str(uuid.uuid4())
    _, project_id, _ = _post_thread_trace(project_name, thread_id)

    traces = list(
        sync_client.threads.traces.list(
            thread_id=thread_id,
            project_id=project_id,
        )
    )
    assert isinstance(traces, list)

    _cleanup_project(sync_client, project_name)


def test_traces_runs_list(sync_client: Client) -> None:
    project_name = _create_project_name("traces_runs")
    trace_id, project_id, start = _post_trace(project_name)

    now = datetime.now(timezone.utc)
    result = sync_client.traces.runs.list(
        trace_id=trace_id,
        project_id=project_id,
        min_start_time=start.isoformat(),
        max_start_time=now.isoformat(),
        selects=["ID", "NAME", "RUN_TYPE"],
    )
    assert result is not None

    _cleanup_project(sync_client, project_name)


# ---------------------------------------------------------------------------
# Async Client tests
# ---------------------------------------------------------------------------


@pytest.fixture
def async_client() -> AsyncClient:
    return AsyncClient()


@pytest.mark.asyncio
async def test_async_runs_create_and_retrieve(async_client: AsyncClient) -> None:
    client = async_client
    sync = Client()
    project_name = _create_project_name("async_runs_create")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    resp = await client.runs.create(
        id=run_id,
        name="async_run_create",
        run_type="chain",
        inputs={"x": 1},
        start_time=now_str,
        session_name=project_name,
    )
    assert resp is not None

    project_id = _get_project_id_or_skip(sync, project_name)
    run = await client.runs.retrieve(
        run_id=run_id,
        project_id=project_id,
        start_time=now_str,
    )
    assert run.id == run_id

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_runs_update(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_runs_update")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await async_client.runs.create(
        id=run_id,
        name="async_update_run",
        run_type="chain",
        inputs={"x": 1},
        start_time=now,
        session_name=project_name,
    )

    resp = await async_client.runs.update(
        run_id=run_id,
        outputs={"y": 2},
        end_time=datetime.now(timezone.utc).isoformat(),
    )
    assert resp is not None

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_runs_ingest_batch(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_batch")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    resp = await async_client.runs.ingest_batch(
        post=[
            {
                "id": run_id,
                "trace_id": run_id,
                "dotted_order": _create_current_dotted_order(now, uuid.UUID(run_id)),
                "name": "async_batch_run",
                "run_type": "chain",
                "inputs": {"n": 1},
                "start_time": now.isoformat(),
                "session_name": project_name,
            }
        ]
    )
    assert resp is not None

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


@pytest.mark.asyncio
async def test_async_runs_stats(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_runs_stats")
    _, project_id, _ = _post_trace(project_name)

    stats = await async_client.runs.stats(session=[project_id])
    assert stats is not None

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_runs_update_2(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_runs_update2")
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await async_client.runs.create(
        id=run_id,
        name="async_update2_run",
        run_type="chain",
        inputs={"x": 1},
        start_time=now,
        session_name=project_name,
    )

    # PATCH requires at least an empty JSON body
    resp = await async_client.runs.update_2(run_id=run_id, extra_body={})
    assert resp is not None

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_threads_query(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_threads_query")
    _, project_id, _ = _post_trace(project_name)

    threads = []
    async for thread in async_client.threads.query(
        project_id=project_id,
    ):
        threads.append(thread)
    assert isinstance(threads, list)

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_threads_traces_list(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_threads_traces")
    thread_id = str(uuid.uuid4())
    _, project_id, _ = _post_thread_trace(project_name, thread_id)

    traces = []
    async for trace in async_client.threads.traces.list(
        thread_id=thread_id,
        project_id=project_id,
    ):
        traces.append(trace)
    assert isinstance(traces, list)

    _cleanup_project(sync, project_name)


@pytest.mark.asyncio
async def test_async_traces_runs_list(async_client: AsyncClient) -> None:
    sync = Client()
    project_name = _create_project_name("async_traces_runs")
    trace_id, project_id, start = _post_trace(project_name)

    now = datetime.now(timezone.utc)
    result = await async_client.traces.runs.list(
        trace_id=trace_id,
        project_id=project_id,
        min_start_time=start.isoformat(),
        max_start_time=now.isoformat(),
        selects=["ID", "NAME", "RUN_TYPE"],
    )
    assert result is not None

    _cleanup_project(sync, project_name)
