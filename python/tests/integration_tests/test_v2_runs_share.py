"""Smoke integration tests for the v2 runs.share resource.

Covers ``Client.runs.share`` (create, delete) against a live backend.
"""

import datetime
import logging
import time
import uuid
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
def project_with_run(langchain_client: Client):
    """Create a project with one root run.

    Yields a dict with run_id, trace_id, and project_id (== session_id).
    """
    project_name = f"__test_v2_runs_share_{uuid7().hex[:12]}"
    if langchain_client.has_project(project_name=project_name):
        langchain_client.delete_project(project_name=project_name)

    run_id = str(uuid7())
    now = datetime.datetime.now(datetime.timezone.utc)
    langchain_client.create_run(
        id=run_id,
        name="run_1",
        inputs={"i": 1},
        run_type="llm",
        project_name=project_name,
        start_time=now,
    )

    def _run_indexed() -> bool:
        return (
            next(langchain_client.list_runs(project_name=project_name, limit=1), None)
            is not None
        )

    _wait_for_sync(_run_indexed, max_sleep_time=90, sleep_time=2)

    run = langchain_client.read_run(run_id)
    project = langchain_client.read_project(project_name=project_name)
    trace_id = str(run.trace_id) if run.trace_id else run_id
    try:
        yield {
            "run_id": run_id,
            "trace_id": trace_id,
            "project_id": str(project.id),
        }
    finally:
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


async def test_runs_share_create(langchain_client: Client, project_with_run) -> None:
    """runs.share.create() mints a valid share token for a run's trace root."""
    run = project_with_run

    async def _create():
        return await langchain_client.runs.share.create(
            run["run_id"],
            session_id=run["project_id"],
            trace_id=run["trace_id"],
        )

    # share.create resolves the trace root from SmithDB, which may lag indexing.
    resp = await _wait_for_async(_create, max_sleep_time=90)
    # Raises ValueError if the token is not a valid UUID.
    assert uuid.UUID(resp.share_token)


async def test_runs_share_delete(langchain_client: Client, project_with_run) -> None:
    """runs.share.delete() removes the share token and is idempotent."""
    run = project_with_run

    async def _create():
        return await langchain_client.runs.share.create(
            run["run_id"],
            session_id=run["project_id"],
            trace_id=run["trace_id"],
        )

    await _wait_for_async(_create, max_sleep_time=90)

    # Delete returns None (204) and is idempotent: a second delete also
    # succeeds. Success is "does not raise".
    await langchain_client.runs.share.delete(
        run["trace_id"], session_id=run["project_id"]
    )
    await langchain_client.runs.share.delete(
        run["trace_id"], session_id=run["project_id"]
    )
