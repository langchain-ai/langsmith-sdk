"""Tests for AsyncExperimentResults edge cases."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from langsmith import schemas as ls_schemas
from langsmith.evaluation._arunner import AsyncExperimentResults
from langsmith.evaluation._runner import ExperimentResultRow


def _make_result(i: int) -> ExperimentResultRow:
    """Create a minimal ExperimentResultRow for testing."""
    example_id = uuid.uuid4()
    run_id = uuid.uuid4()
    return ExperimentResultRow(
        run=ls_schemas.Run(
            id=run_id,
            name=f"run-{i}",
            run_type="chain",
            inputs={"in": i},
            outputs={"out": i},
            start_time=datetime.now(tz=timezone.utc),
            trace_id=run_id,
            dotted_order=f"20210901T000000000000{run_id}",
        ),
        example=ls_schemas.Example(
            id=example_id,
            dataset_id=uuid.uuid4(),
            inputs={"in": i},
            created_at=datetime.now(tz=timezone.utc),
        ),
        evaluation_results={"results": []},
    )


def _make_manager(
    results: list[ExperimentResultRow],
    summary: dict | None = None,
    error_after: int | None = None,
    summary_error: BaseException | None = None,
):
    """Build a mock _AsyncExperimentManager.

    Args:
        results: Results to yield from aget_results().
        summary: Summary scores to return. Defaults to empty.
        error_after: If set, raise RuntimeError after yielding this many results.
        summary_error: If set, raise this from aget_summary_scores().
    """
    manager = MagicMock()
    manager.experiment_name = "test-experiment"

    async def _aget_results():
        for i, r in enumerate(results):
            if error_after is not None and i >= error_after:
                raise RuntimeError(f"producer failed at index {i}")
            yield r

    manager.aget_results = _aget_results

    if summary_error is not None:
        manager.aget_summary_scores = AsyncMock(side_effect=summary_error)
    else:
        manager.aget_summary_scores = AsyncMock(return_value=summary or {"results": []})

    return manager


async def test_iterates_all_results():
    """All results from the producer are yielded to the consumer."""
    items = [_make_result(i) for i in range(5)]
    manager = _make_manager(items)

    results = AsyncExperimentResults(manager)
    collected = [r async for r in results]

    assert len(collected) == 5
    for i, r in enumerate(collected):
        assert r["run"].name == f"run-{i}"


async def test_empty_results():
    """Iterating with zero results immediately stops."""
    manager = _make_manager([])
    results = AsyncExperimentResults(manager)

    collected = [r async for r in results]
    assert collected == []


async def test_exception_propagates_from_producer():
    """If aget_results() raises, __anext__ surfaces the real exception."""
    items = [_make_result(i) for i in range(5)]
    manager = _make_manager(items, error_after=3)

    results = AsyncExperimentResults(manager)
    collected = []
    with pytest.raises(RuntimeError, match="producer failed at index 3"):
        async for r in results:
            collected.append(r)

    # The 3 results yielded before the error should have been delivered.
    assert len(collected) == 3


async def test_summary_error_propagates():
    """If aget_summary_scores() raises, __anext__ surfaces the exception."""
    items = [_make_result(i) for i in range(2)]
    manager = _make_manager(items, summary_error=RuntimeError("summary failed"))

    results = AsyncExperimentResults(manager)
    collected = []
    with pytest.raises(RuntimeError, match="summary failed"):
        async for r in results:
            collected.append(r)

    # All items were yielded before the summary error.
    assert len(collected) == 2


async def test_wait_raises_on_producer_error():
    """.wait() re-raises the producer exception."""
    items = [_make_result(i) for i in range(3)]
    manager = _make_manager(items, error_after=1)

    results = AsyncExperimentResults(manager)
    with pytest.raises(RuntimeError, match="producer failed at index 1"):
        await results.wait()


async def test_wait_completes_on_success():
    """.wait() returns cleanly when the producer succeeds."""
    items = [_make_result(i) for i in range(3)]
    manager = _make_manager(items)

    results = AsyncExperimentResults(manager)
    await results.wait()
    assert len(results) == 3


async def test_len_reflects_buffered_results():
    """len() reflects how many results the producer has buffered so far."""
    items = [_make_result(i) for i in range(4)]
    manager = _make_manager(items)

    results = AsyncExperimentResults(manager)
    # Wait for the producer to finish.
    await results.wait()
    assert len(results) == 4
