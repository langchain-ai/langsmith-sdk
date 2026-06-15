"""Unit tests for static feedback-key extraction from evaluator source."""

import pytest

from langsmith.evaluation._key_extraction import (
    _extract_code_evaluator_feedback_keys,
    _safe_extract_feedback_keys,
)
from langsmith.evaluation.evaluator import EvaluationResult, EvaluationResults


def _dict_literal(run, example):
    return {"key": "correctness", "score": 1}


def _dict_call(run, example):
    return dict(key="relevance", score=1)


def _evaluation_result(run, example):
    return EvaluationResult(key="accuracy", score=1)


def _evaluation_results_list(run, example):
    return EvaluationResults(
        results=[
            EvaluationResult(key="k1", score=1),
            EvaluationResult(key="k2", score=0),
        ]
    )


def _evaluation_results_mixed_elements(run, example):
    return EvaluationResults(
        results=[
            EvaluationResult(key="d1", score=1),
            dict(key="d2", score=0),
        ]
    )


def _results_dict_form(run, example):
    return {"results": [{"key": "x", "score": 1}, {"key": "y", "score": 0}]}


def _results_from_variable(run, example):
    results = [
        EvaluationResult(key="a", score=1),
        EvaluationResult(key="b", score=0),
    ]
    return EvaluationResults(results=results)


async def _async_dict_literal(inputs, outputs):
    return {"key": "async_key", "score": 1}


def _dynamic_key(run, example):
    computed = "computed_at_runtime"
    return {"key": computed, "score": 1}


@pytest.mark.parametrize(
    "func,expected",
    [
        (_dict_literal, ["correctness"]),
        (_dict_call, ["relevance"]),
        (_evaluation_result, ["accuracy"]),
        (_evaluation_results_list, ["k1", "k2"]),
        (_results_dict_form, ["x", "y"]),
        (_results_from_variable, ["a", "b"]),
        (_async_dict_literal, ["async_key"]),
    ],
)
def test_extract_code_evaluator_feedback_keys(func, expected):
    assert _extract_code_evaluator_feedback_keys(func) == expected


def test_dict_element_inside_evaluation_results_is_not_extracted():
    # Known limitation: within ``EvaluationResults(results=[...])`` only
    # ``EvaluationResult(...)`` elements are parsed; a ``dict(...)`` element is
    # skipped. (The dict-form ``{"results": [...]}`` branch does handle both.)
    assert _extract_code_evaluator_feedback_keys(
        _evaluation_results_mixed_elements
    ) == ["d1"]


def test_falls_back_to_function_name_for_dynamic_key():
    # No literal `key` to read, so extraction falls back to the function name.
    assert _extract_code_evaluator_feedback_keys(_dynamic_key) == ["_dynamic_key"]


def test_safe_extract_returns_empty_when_source_unavailable():
    # Built-ins have no inspectable source; inspect.getsource raises -> [].
    assert _safe_extract_feedback_keys(len) == []


def test_safe_extract_matches_direct_extraction_on_happy_path():
    assert _safe_extract_feedback_keys(_dict_literal) == ["correctness"]
