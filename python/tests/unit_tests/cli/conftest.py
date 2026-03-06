"""Shared test fixtures."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client(mocker):
    """Mock langsmith.Client."""
    client = MagicMock()
    mocker.patch("langsmith.cli.config.Client", return_value=client)
    return client


def make_run(
    run_id=None,
    trace_id=None,
    name="test-run",
    run_type="chain",
    parent_run_id=None,
    start_time=None,
    end_time=None,
    status="success",
    inputs=None,
    outputs=None,
    error=None,
    extra=None,
    tags=None,
    prompt_tokens=None,
    completion_tokens=None,
    total_tokens=None,
    prompt_cost=None,
    completion_cost=None,
    total_cost=None,
):
    """Create a mock Run object."""
    if run_id is None:
        run_id = uuid.uuid4()
    if trace_id is None:
        trace_id = uuid.uuid4()
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    if end_time is None:
        end_time = start_time + timedelta(seconds=1)

    return SimpleNamespace(
        id=run_id,
        trace_id=trace_id,
        name=name,
        run_type=run_type,
        parent_run_id=parent_run_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        inputs=inputs or {},
        outputs=outputs or {},
        error=error,
        extra=extra or {"metadata": {}},
        tags=tags or [],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_cost=prompt_cost,
        completion_cost=completion_cost,
        total_cost=total_cost,
    )


def make_dataset(
    dataset_id=None,
    name="test-dataset",
    description=None,
    example_count=10,
    data_type=None,
    created_at=None,
):
    """Create a mock Dataset object."""
    if dataset_id is None:
        dataset_id = uuid.uuid4()
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    dt = SimpleNamespace(value="kv") if data_type is None else data_type

    return SimpleNamespace(
        id=dataset_id,
        name=name,
        description=description,
        data_type=dt,
        example_count=example_count,
        created_at=created_at,
    )


def make_example(
    example_id=None,
    dataset_id=None,
    inputs=None,
    outputs=None,
    metadata=None,
    split=None,
    created_at=None,
):
    """Create a mock Example object."""
    if example_id is None:
        example_id = uuid.uuid4()
    if dataset_id is None:
        dataset_id = uuid.uuid4()
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=example_id,
        dataset_id=dataset_id,
        inputs=inputs or {"question": "test"},
        outputs=outputs or {"answer": "test"},
        metadata=metadata or {},
        split=split,
        created_at=created_at,
    )
