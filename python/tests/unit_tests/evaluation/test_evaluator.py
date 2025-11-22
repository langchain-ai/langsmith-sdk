import asyncio
import logging
import uuid
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from langsmith import schemas
from langsmith.evaluation.evaluator import (
    ComparisonEvaluationResult,
    DynamicComparisonRunEvaluator,
    DynamicRunEvaluator,
    EvaluationResult,
    EvaluationResults,
    Example,
    Run,
    run_evaluator,
)
from langsmith.run_helpers import tracing_context


@pytest.fixture
def run_1() -> Run:
    run = MagicMock()
    run.inputs = {"input": "1"}
    run.outputs = {"output": "2"}
    return run


@pytest.fixture
def example_1():
    example = MagicMock()
    example.inputs = {"input": "1"}
    example.outputs = {"output": "2"}
    return example


def test_run_evaluator_decorator(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> EvaluationResult:
        return EvaluationResult(key="test", score=1.0)

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


async def test_dynamic_comparison_run_evaluator():
    def foo(runs: list, example):
        return ComparisonEvaluationResult(key="bar", scores={uuid.uuid4(): 3.1})

    async def afoo(runs: list, example):
        return ComparisonEvaluationResult(key="bar", scores={uuid.uuid4(): 3.1})

    evaluators = [
        DynamicComparisonRunEvaluator(foo),
        DynamicComparisonRunEvaluator(afoo),
        DynamicComparisonRunEvaluator(foo, afoo),
    ]
    for e in evaluators:
        res = await e.acompare_runs([], None)
        assert res.key == "bar"
        repr(e)


def test_run_evaluator_decorator_dict(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"key": "test", "score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


def test_run_evaluator_decorator_dict_no_key(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0


def test_run_evaluator_decorator_dict_with_comment(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"score": 1.0, "comment": "test"}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0
    assert result.comment == "test"


def test_run_evaluator_decorator_multi_return(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {
            "results": [
                {"key": "test", "score": 1.0},
                {"key": "test2", "score": 2.0},
            ]
        }

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0


def test_run_evaluator_decorator_multi_return_no_key(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {
            "results": [
                {"score": 1.0},
                {"key": "test2", "score": 2.0},
            ]
        }

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with pytest.raises(ValueError):
        with tracing_context(enabled=False):
            sample_evaluator.evaluate_run(run_1, example_1)


def test_run_evaluator_decorator_return_multi_evaluation_result(
    run_1: Run, example_1: Example
):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> EvaluationResults:
        return EvaluationResults(
            results=[
                EvaluationResult(key="test", score=1.0),
                EvaluationResult(key="test2", score=2.0),
            ]
        )

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = sample_evaluator.evaluate_run(run_1, example_1)
    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0


async def test_run_evaluator_decorator_async(run_1: Run, example_1: Example):
    @run_evaluator
    async def sample_evaluator(
        run: Run, example: Optional[Example]
    ) -> EvaluationResult:
        await asyncio.sleep(0.01)
        return EvaluationResult(key="test", score=1.0)

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


async def test_run_evaluator_decorator_dict_async(run_1: Run, example_1: Example):
    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return {"key": "test", "score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


async def test_run_evaluator_decorator_dict_no_key_async(
    run_1: Run, example_1: Example
):
    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return {"score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0


async def test_run_evaluator_decorator_dict_with_comment_async(
    run_1: Run, example_1: Example
):
    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return {"score": 1.0, "comment": "test"}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0
    assert result.comment == "test"


async def test_run_evaluator_decorator_multi_return_async(
    run_1: Run, example_1: Example
):
    _response = {
        "results": [
            {"key": "test", "score": 1.0},
            {"key": "test2", "score": 2.0},
        ]
    }

    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return _response

    @run_evaluator
    def sample_sync_evaluator(run: Run, example: Optional[Example]) -> dict:
        return _response

    assert isinstance(sample_evaluator, DynamicRunEvaluator)

    result = await sample_evaluator.aevaluate_run(run_1, example_1)

    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0
    with tracing_context(enabled=False):
        aresult = await sample_sync_evaluator.aevaluate_run(run_1, example_1)
    sresult = sample_sync_evaluator.evaluate_run(run_1, example_1)
    scores = [result.score for result in result["results"]]
    assert (
        scores
        == [r.score for r in sresult["results"]]
        == [r.score for r in aresult["results"]]
    )


async def test_run_evaluator_decorator_multi_return_no_key_async(
    run_1: Run, example_1: Example
):
    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return {
            "results": [
                {"score": 1.0},
                {"key": "test2", "score": 2.0},
            ]
        }

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with pytest.raises(ValueError):
        with tracing_context(enabled=False):
            await sample_evaluator.aevaluate_run(run_1, example_1)


async def test_run_evaluator_decorator_return_multi_evaluation_result_async(
    run_1: Run, example_1: Example
):
    @run_evaluator
    async def sample_evaluator(
        run: Run, example: Optional[Example]
    ) -> EvaluationResults:
        await asyncio.sleep(0.01)
        return EvaluationResults(
            results=[
                EvaluationResult(key="test", score=1.0),
                EvaluationResult(key="test2", score=2.0),
            ]
        )

    assert isinstance(sample_evaluator, DynamicRunEvaluator)
    with tracing_context(enabled=False):
        result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0


@pytest.mark.parametrize("response", [None, {}, []])
async def test_evaluator_raises_for_null_output(response: Any):
    @run_evaluator  # type: ignore
    def bad_evaluator(run: schemas.Run, example: schemas.Example):
        return response

    @run_evaluator  # type: ignore
    async def abad_evaluator(run: schemas.Run, example: schemas.Example):
        return response

    fake_run = MagicMock()
    fake_example = MagicMock()

    with pytest.raises(ValueError, match="Expected a non-empty "):
        bad_evaluator.evaluate_run(fake_run, fake_example)

    with pytest.raises(ValueError, match="Expected a non-empty "):
        await bad_evaluator.aevaluate_run(fake_run, fake_example)

    with pytest.raises(ValueError, match="Expected a non-empty "):
        await abad_evaluator.aevaluate_run(fake_run, fake_example)


@pytest.mark.parametrize("response", [[5], {"accuracy": 5}])
async def test_evaluator_raises_for_bad_output(response: Any):
    @run_evaluator  # type: ignore
    def bad_evaluator(run: schemas.Run, example: schemas.Example):
        return response

    @run_evaluator  # type: ignore
    async def abad_evaluator(run: schemas.Run, example: schemas.Example):
        return response

    fake_run = MagicMock()
    fake_example = MagicMock()

    with pytest.raises(ValueError, match="Expected"):
        bad_evaluator.evaluate_run(fake_run, fake_example)

    with pytest.raises(ValueError, match="Expected"):
        await bad_evaluator.aevaluate_run(fake_run, fake_example)

    with pytest.raises(ValueError, match="Expected"):
        await abad_evaluator.aevaluate_run(fake_run, fake_example)


def test_check_value_non_numeric(caplog):
    # Test when score is None and value is numeric
    with caplog.at_level(logging.WARNING):
        EvaluationResult(key="test", value=5)

    assert (
        "Numeric values should be provided in the 'score' field, not 'value'. Got: 5"
        in caplog.text
    )

    # Test when score is provided and value is numeric (should not log)
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        EvaluationResult(key="test", score=5, value="non-numeric")

    assert (
        "Numeric values should be provided in the 'score' field, not 'value'."
        not in caplog.text
    )

    # Test when both score and value are None (should not log)
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        EvaluationResult(key="test")

    assert (
        "Numeric values should be provided in the 'score' field, not 'value'."
        not in caplog.text
    )

    # Test when value is non-numeric (should not log)
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        EvaluationResult(key="test", value="non-numeric")

    assert (
        "Numeric values should be provided in the 'score' field, not 'value'."
        not in caplog.text
    )
