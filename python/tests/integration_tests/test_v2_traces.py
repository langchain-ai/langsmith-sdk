"""Smoke integration tests for the v2 traces resource.

Covers `Client.traces` (query, list_runs), exposed in #3162.
"""

import datetime
import logging
import time
from datetime import timedelta
from typing import Any, Callable

import pytest

from langsmith import uuid7
from langsmith.client import Client
from langsmith.utils import get_env_var

logger = logging.getLogger(__name__)


def _wait_for_sync(
    condition: Callable[[], bool],
    max_sleep_time: int = 60,
    sleep_time: int = 3,
) -> None:
    start = time.time()
    while time.time() - start < max_sleep_time:
        try:
            if condition():
                return
        except Exception:
            pass
        time.sleep(sleep_time)
    raise ValueError(f"Condition not met within {max_sleep_time}s")


async def _wait_for_async(
    condition: Callable[[], Any],
    max_sleep_time: int = 60,
    sleep_time: int = 3,
) -> Any:
    """Poll `condition` until it returns a truthy value, then return it."""
    start = time.time()
    while time.time() - start < max_sleep_time:
        try:
            result = await condition()
            if result:
                return result
        except Exception:
            pass
        time.sleep(sleep_time)
    raise ValueError(f"Condition not met within {max_sleep_time}s")


@pytest.fixture
def langchain_client() -> Client:
    get_env_var.cache_clear()
    return Client()


@pytest.fixture
def project_with_runs(langchain_client: Client):
    """Create a project with two runs.

    Yields (project_id, min_start_time, max_start_time).
    """
    project_name = f"__test_v2_traces_{uuid7().hex[:12]}"
    if langchain_client.has_project(project_name=project_name):
        langchain_client.delete_project(project_name=project_name)

    now = datetime.datetime.now(datetime.timezone.utc)
    langchain_client.create_run(
        name="run_1",
        inputs={"i": 1},
        run_type="llm",
        project_name=project_name,
        start_time=now,
    )
    langchain_client.create_run(
        name="run_2",
        inputs={"i": 2},
        run_type="llm",
        project_name=project_name,
        start_time=now + timedelta(seconds=1),
    )

    def _runs_indexed() -> bool:
        return (
            next(langchain_client.list_runs(project_name=project_name, limit=1), None)
            is not None
        )

    _wait_for_sync(_runs_indexed, max_sleep_time=30, sleep_time=2)

    project = langchain_client.read_project(project_name=project_name)
    min_start_time = now - timedelta(hours=1)
    max_start_time = now + timedelta(minutes=5)
    try:
        yield str(project.id), min_start_time, max_start_time
    finally:
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


async def test_traces_query(langchain_client: Client, project_with_runs) -> None:
    """traces.query() returns a page of traces (root runs) for the project."""
    project_id, min_start_time, max_start_time = project_with_runs

    async def _ready():
        page = await langchain_client.traces.query(
            project_id=project_id,
            page_size=10,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
        )
        return page if page.items else None

    page = await _wait_for_async(_ready, max_sleep_time=60)
    assert len(page.items) > 0


async def test_traces_list_runs(langchain_client: Client, project_with_runs) -> None:
    """traces.list_runs() returns the runs belonging to a trace."""
    project_id, min_start_time, max_start_time = project_with_runs

    page = await langchain_client.traces.query(
        project_id=project_id,
        page_size=10,
        min_start_time=min_start_time,
        max_start_time=max_start_time,
    )
    assert len(page.items) > 0
    root_run = page.items[0].root_run
    assert root_run is not None
    trace_id = str(root_run.id)

    response = await langchain_client.traces.list_runs(trace_id, project_id=project_id)
    assert response.items is not None
    assert len(response.items) > 0
