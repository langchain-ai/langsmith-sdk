"""Tests for ExperimentResults edge cases."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from langsmith import schemas as ls_schemas
from langsmith.evaluation._runner import ExperimentResultRow, ExperimentResults


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
    """Build a mock _ExperimentManager.

    Args:
        results: Results to yield from get_results().
        summary: Summary scores to return. Defaults to empty.
        error_after: If set, raise RuntimeError after yielding this many results.
        summary_error: If set, raise this from get_summary_scores().
    """
    manager = MagicMock()
    manager.experiment_name = "test-experiment"

    def _get_results():
        for i, r in enumerate(results):
            if error_after is not None and i >= error_after:
                raise RuntimeError(f"producer failed at index {i}")
            yield r

    manager.get_results = _get_results

    if summary_error is not None:
        manager.get_summary_scores = MagicMock(side_effect=summary_error)
    else:
        manager.get_summary_scores = MagicMock(return_value=summary or {"results": []})

    return manager


def test_iterates_all_results():
    """All results from the producer are yielded to the consumer."""
    items = [_make_result(i) for i in range(5)]
    manager = _make_manager(items)

    results = ExperimentResults(manager, blocking=False)
    collected = list(results)

    assert len(collected) == 5
    for i, r in enumerate(collected):
        assert r["run"].name == f"run-{i}"


def test_empty_results():
    """Iterating with zero results immediately stops."""
    manager = _make_manager([])
    results = ExperimentResults(manager, blocking=False)

    collected = list(results)
    assert collected == []


def test_exception_propagates_from_producer():
    """If get_results() raises, __iter__ surfaces the real exception."""
    items = [_make_result(i) for i in range(5)]
    manager = _make_manager(items, error_after=3)

    results = ExperimentResults(manager, blocking=False)
    collected = []
    with pytest.raises(RuntimeError, match="producer failed at index 3"):
        for r in results:
            collected.append(r)

    # The 3 results yielded before the error should have been delivered.
    assert len(collected) == 3


def test_summary_error_propagates():
    """If get_summary_scores() raises, __iter__ surfaces the exception."""
    items = [_make_result(i) for i in range(2)]
    manager = _make_manager(items, summary_error=RuntimeError("summary failed"))

    results = ExperimentResults(manager, blocking=False)
    collected = []
    with pytest.raises(RuntimeError, match="summary failed"):
        for r in results:
            collected.append(r)

    # All items were yielded before the summary error.
    assert len(collected) == 2


def test_wait_raises_on_producer_error():
    """.wait() re-raises the producer exception."""
    items = [_make_result(i) for i in range(3)]
    manager = _make_manager(items, error_after=1)

    results = ExperimentResults(manager, blocking=False)
    with pytest.raises(RuntimeError, match="producer failed at index 1"):
        results.wait()


def test_wait_completes_on_success():
    """.wait() returns cleanly when the producer succeeds."""
    items = [_make_result(i) for i in range(3)]
    manager = _make_manager(items)

    results = ExperimentResults(manager, blocking=False)
    results.wait()
    assert len(results) == 3


def test_len_reflects_buffered_results():
    """len() reflects how many results the producer has buffered so far."""
    items = [_make_result(i) for i in range(4)]
    manager = _make_manager(items)

    results = ExperimentResults(manager, blocking=False)
    results.wait()
    assert len(results) == 4


def test_blocking_mode_propagates_error():
    """In blocking mode, the error propagates during __init__."""
    items = [_make_result(i) for i in range(3)]
    manager = _make_manager(items, error_after=1)

    # In blocking mode, _process_data runs in __init__ — error is stored,
    # then surfaced when iterating.
    results = ExperimentResults(manager, blocking=True)
    collected = []
    with pytest.raises(RuntimeError, match="producer failed at index 1"):
        for r in results:
            collected.append(r)

    assert len(collected) == 1
