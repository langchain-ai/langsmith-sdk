import asyncio
from typing import Optional
from unittest.mock import MagicMock

import pytest

from langsmith.evaluation.evaluator import (
    DynamicRunEvaluator,
    EvaluationResult,
    EvaluationResults,
    Example,
    Run,
    run_evaluator,
)


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

    result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


def test_run_evaluator_decorator_dict(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"key": "test", "score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)

    result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "test"
    assert result.score == 1.0


def test_run_evaluator_decorator_dict_no_key(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"score": 1.0}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)

    result = sample_evaluator.evaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0


def test_run_evaluator_decorator_dict_with_comment(run_1: Run, example_1: Example):
    @run_evaluator
    def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        return {"score": 1.0, "comment": "test"}

    assert isinstance(sample_evaluator, DynamicRunEvaluator)

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

    result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert isinstance(result, EvaluationResult)
    assert result.key == "sample_evaluator"
    assert result.score == 1.0
    assert result.comment == "test"


async def test_run_evaluator_decorator_multi_return_async(
    run_1: Run, example_1: Example
):
    @run_evaluator
    async def sample_evaluator(run: Run, example: Optional[Example]) -> dict:
        await asyncio.sleep(0.01)
        return {
            "results": [
                {"key": "test", "score": 1.0},
                {"key": "test2", "score": 2.0},
            ]
        }

    assert isinstance(sample_evaluator, DynamicRunEvaluator)

    result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0


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

    result = await sample_evaluator.aevaluate_run(run_1, example_1)
    assert not isinstance(result, EvaluationResult)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0].key == "test"
    assert result["results"][0].score == 1.0
    assert result["results"][1].key == "test2"
    assert result["results"][1].score == 2.0
