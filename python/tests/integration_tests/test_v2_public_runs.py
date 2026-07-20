"""Smoke integration tests for the v2 public.runs resource.

Covers ``Client.public.runs`` (retrieve, query) against a live backend. Public
shared-run reads are authenticated by the share token in the path; the client's
API key is created only to mint that token via ``runs.share.create``.
"""

import datetime
import logging
import time
from typing import Any, Callable

import pytest

from langsmith import uuid7
from langsmith.client import Client
from langsmith.utils import get_env_var

logger = logging.getLogger(__name__)

# Public run fields to request; START_TIME is needed as the retrieve coordinate.
_SELECTS = ["ID", "NAME", "RUN_TYPE", "STATUS", "START_TIME"]


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
async def shared_run(langchain_client: Client):
    """Create a project with one root run and share it.

    Yields a dict with run_id, project_id, and share_token.
    """
    project_name = f"__test_v2_public_runs_{uuid7().hex[:12]}"
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
    project_id = str(project.id)
    trace_id = str(run.trace_id) if run.trace_id else run_id

    async def _create_share():
        return await langchain_client.runs.share.create(
            run_id, session_id=project_id, trace_id=trace_id
        )

    # share.create resolves the trace root from SmithDB, which may lag indexing.
    resp = await _wait_for_async(_create_share, max_sleep_time=90)

    try:
        yield {
            "run_id": run_id,
            "project_id": project_id,
            "share_token": resp.share_token,
        }
    finally:
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


async def test_public_runs_query(langchain_client: Client, shared_run) -> None:
    """public.runs.query() returns the shared trace's runs by share token."""
    share_token = shared_run["share_token"]
    run_id = shared_run["run_id"]

    async def _ready():
        page = await langchain_client.public.runs.query(share_token, selects=_SELECTS)
        return page if any(str(i.id) == run_id for i in page.items) else None

    page = await _wait_for_async(_ready, max_sleep_time=90)
    assert run_id in {str(i.id) for i in page.items}


async def test_public_runs_retrieve(langchain_client: Client, shared_run) -> None:
    """public.runs.retrieve() returns a single run by (share token, id, start_time)."""
    share_token = shared_run["share_token"]
    run_id = shared_run["run_id"]

    async def _retrieve():
        # Derive the exact start_time coordinate from the public read path itself,
        # so it matches whatever the backend stored (retrieve is a point lookup).
        page = await langchain_client.public.runs.query(share_token, selects=_SELECTS)
        item = next((i for i in page.items if str(i.id) == run_id), None)
        if item is None or item.start_time is None:
            return None
        return await langchain_client.public.runs.retrieve(
            run_id,
            share_token=share_token,
            selects=_SELECTS,
            start_time=item.start_time,
        )

    run = await _wait_for_async(_retrieve, max_sleep_time=90)
    assert str(run.id) == run_id
