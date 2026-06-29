"""Integration tests for the v2 datasets resource (experiment_runs endpoint).

Covers langchainplus#28358:
  - POST /v2/datasets/{id}/experiment-runs  (new, cursor pagination)
  - POST /api/v1/datasets/{id}/runs  (unchanged, offset pagination, bare-list response)
"""

import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine

import pytest

from langsmith import uuid7
from langsmith.client import Client
from langsmith.utils import get_env_var

logger = logging.getLogger(__name__)

_dataset_deletion_lock = threading.Lock()


def _safe_delete_dataset(client: Client, dataset_name: str) -> None:
    with _dataset_deletion_lock:
        try:
            client.delete_dataset(dataset_name=dataset_name)
        except Exception as e:
            logger.warning(f"Failed to delete dataset: {e}")


async def _wait_for_async(
    condition: Callable[[], Coroutine],
    max_sleep_time: int = 60,
    sleep_time: int = 3,
) -> None:
    import time

    start = time.time()
    while time.time() - start < max_sleep_time:
        try:
            if await condition():
                return
        except Exception:
            pass
        await asyncio.sleep(sleep_time)
    raise ValueError(f"Condition not met within {max_sleep_time}s")


def _setup_experiment(
    client: Client, dataset_name: str, num_examples: int = 3
) -> tuple:
    """Create a dataset + examples, run evaluate, return (dataset, experiment_id)."""
    if client.has_dataset(dataset_name=dataset_name):
        _safe_delete_dataset(client, dataset_name)
    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(
        inputs=[{"q": str(i)} for i in range(num_examples)],
        outputs=[{"a": str(i)} for i in range(num_examples)],
        dataset_id=dataset.id,
    )
    results = client.evaluate(lambda i: {"a": "x"}, data=dataset_name)
    project = client.read_project(project_name=results.experiment_name)
    return dataset, str(project.id)


@pytest.fixture
def langchain_client() -> Client:
    get_env_var.cache_clear()
    return Client(
        info={
            "instance_flags": {
                "dataset_examples_multipart_enabled": True,
                "examples_multipart_enabled": True,
                "zstd_compression_enabled": True,
            }
        }
    )


# ---------------------------------------------------------------------------
# v2 experiment-runs tests
# ---------------------------------------------------------------------------


async def test_v2_experiment_runs_create(langchain_client: Client) -> None:
    """v2 endpoint returns {items: [...], next_cursor} — not a bare list."""
    dataset_name = "__test_v2_exp_runs_" + uuid7().hex
    dataset, experiment_id = _setup_experiment(langchain_client, dataset_name)

    async def _ready() -> bool:
        page = await langchain_client.datasets.experiment_runs.create(
            str(dataset.id), experiment_ids=[experiment_id], page_size=10
        )
        return len(page.items) > 0

    await _wait_for_async(_ready, max_sleep_time=30)

    page = await langchain_client.datasets.experiment_runs.create(
        str(dataset.id), experiment_ids=[experiment_id], page_size=10
    )

    assert page.items is not None
    assert len(page.items) == 3
    assert hasattr(page, "next_cursor")
    item = page.items[0]
    assert item.id is not None
    assert item.inputs is not None

    _safe_delete_dataset(langchain_client, dataset_name)


async def test_v2_experiment_runs_cursor_pagination(langchain_client: Client) -> None:
    """page_size=1 + following next_cursor returns all examples without duplicates."""
    dataset_name = "__test_v2_exp_cursor_" + uuid7().hex
    dataset, experiment_id = _setup_experiment(
        langchain_client, dataset_name, num_examples=3
    )

    async def _ready() -> bool:
        page = await langchain_client.datasets.experiment_runs.create(
            str(dataset.id), experiment_ids=[experiment_id], page_size=10
        )
        return len(page.items) == 3

    await _wait_for_async(_ready, max_sleep_time=30)

    all_items: list = []
    cursor = None
    for _ in range(10):
        kwargs: dict[str, Any] = {"experiment_ids": [experiment_id], "page_size": 1}
        if cursor:
            kwargs["cursor"] = cursor
        page = await langchain_client.datasets.experiment_runs.create(
            str(dataset.id), **kwargs
        )
        all_items.extend(page.items)
        cursor = page.next_cursor
        if not cursor:
            break

    assert len(all_items) == 3
    assert len({item.id for item in all_items}) == 3

    _safe_delete_dataset(langchain_client, dataset_name)


# ---------------------------------------------------------------------------
# v1 backward-compat regression
# ---------------------------------------------------------------------------


async def test_v1_runs_create_backward_compat(langchain_client: Client) -> None:
    """v1 endpoint still returns a bare list (not {items:...}) after de-publicization."""  # noqa: E501
    dataset_name = "__test_v1_runs_compat_" + uuid7().hex
    dataset, experiment_id = _setup_experiment(
        langchain_client, dataset_name, num_examples=1
    )

    async def _ready() -> bool:
        resp = await langchain_client.datasets.runs.create(
            str(dataset.id),
            session_ids=[experiment_id],
            limit=10,
            offset=0,
            preview=True,
        )
        return isinstance(resp, list) and len(resp) >= 1

    await _wait_for_async(_ready, max_sleep_time=30)

    resp = await langchain_client.datasets.runs.create(
        str(dataset.id), session_ids=[experiment_id], limit=10, offset=0, preview=True
    )
    assert isinstance(resp, list)
    assert len(resp) >= 1
    assert resp[0].id is not None

    _safe_delete_dataset(langchain_client, dataset_name)
