"""Unit tests for langsmith.beta._evals."""

import uuid
from datetime import datetime, timezone
from unittest import mock

import pytest

from langsmith import beta
from langsmith import schemas as ls_schemas
from langsmith.evaluation import EvaluationResult


def _stub_run() -> ls_schemas.Run:
    run_id = uuid.uuid4()
    return ls_schemas.Run(
        id=run_id,
        name="stub",
        run_type="chain",
        start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        trace_id=run_id,
    )


def test_compute_test_metrics_deprecation_warning() -> None:
    """compute_test_metrics is deprecated with no replacement."""
    client = mock.Mock()
    client.evaluate_run.return_value = EvaluationResult(key="stub", score=1)
    run = _stub_run()

    def evaluator(run: ls_schemas.Run, example=None) -> dict:
        return {"key": "stub", "score": 1}

    with mock.patch(
        "langsmith.beta._evals._load_nested_traces", return_value=[run]
    ) as load_traces:
        with pytest.warns(
            DeprecationWarning, match="compute_test_metrics\\(\\) is deprecated"
        ):
            beta.compute_test_metrics(
                "some-project", evaluators=[evaluator], client=client
            )

    load_traces.assert_called_once()
    client.evaluate_run.assert_called_once()
