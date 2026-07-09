"""Smoke integration tests for the v2 threads resource.

Covers `Client.threads` (query, list_traces, stats), exposed in #3162.
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
            logger.debug("Error checking sync condition", exc_info=True)
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
            logger.debug("Error checking async condition", exc_info=True)
        time.sleep(sleep_time)
    raise ValueError(f"Condition not met within {max_sleep_time}s")


@pytest.fixture
def langchain_client() -> Client:
    get_env_var.cache_clear()
    return Client()


@pytest.fixture
def project_with_thread(langchain_client: Client):
    """Create a project with two runs sharing a thread_id.

    Yields (project_id, thread_id, min_start_time, max_start_time).
    """
    project_name = f"__test_v2_threads_{uuid7().hex[:12]}"
    if langchain_client.has_project(project_name=project_name):
        langchain_client.delete_project(project_name=project_name)

    thread_id = f"thread-{uuid7().hex[:8]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    # Backend derives thread_id from extra.metadata; set session_id/conversation_id
    # to None so thread_id is used for grouping.
    meta = {
        "metadata": {
            "thread_id": thread_id,
            "session_id": None,
            "conversation_id": None,
        }
    }
    langchain_client.create_run(
        name="run_1",
        inputs={"i": 1},
        run_type="llm",
        project_name=project_name,
        start_time=now,
        extra=meta,
    )
    langchain_client.create_run(
        name="run_2",
        inputs={"i": 2},
        run_type="llm",
        project_name=project_name,
        start_time=now + timedelta(seconds=1),
        extra=meta,
    )

    def _runs_indexed() -> bool:
        return (
            next(langchain_client.list_runs(project_name=project_name, limit=1), None)
            is not None
        )

    _wait_for_sync(_runs_indexed, max_sleep_time=90, sleep_time=2)

    project = langchain_client.read_project(project_name=project_name)
    min_start_time = now - timedelta(hours=1)
    max_start_time = now + timedelta(minutes=5)
    try:
        yield str(project.id), thread_id, min_start_time, max_start_time
    finally:
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


async def test_threads_query(langchain_client: Client, project_with_thread) -> None:
    """threads.query() returns a page containing the created thread."""
    project_id, thread_id, min_start_time, max_start_time = project_with_thread

    async def _ready():
        page = await langchain_client.threads.query(
            project_id=project_id,
            page_size=10,
            min_start_time=min_start_time,
            max_start_time=max_start_time,
        )
        return next((t for t in page.items if t.thread_id == thread_id), None)

    thread = await _wait_for_async(_ready, max_sleep_time=90)
    assert thread.thread_id == thread_id


async def test_threads_list_traces(
    langchain_client: Client, project_with_thread
) -> None:
    """threads.list_traces() returns traces belonging to the thread."""
    project_id, thread_id, _, _ = project_with_thread

    async def _ready():
        page = await langchain_client.threads.list_traces(
            thread_id, project_id=project_id, page_size=10
        )
        return page if page.items else None

    page = await _wait_for_async(_ready, max_sleep_time=60)
    assert len(page.items) > 0


async def test_threads_stats(langchain_client: Client, project_with_thread) -> None:
    """threads.stats() returns an aggregate stats response for the thread."""
    project_id, thread_id, _, _ = project_with_thread
    stats = await langchain_client.threads.stats(
        thread_id, selects=["TURNS"], session_id=project_id
    )
    assert stats is not None
