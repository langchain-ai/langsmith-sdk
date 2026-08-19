"""Benchmarks for JSON serialization.

`dumps_json` sits on the hot path of every traced run: each run payload (and
each of its inputs / outputs / events / extra fields) goes through it before it
is sent to LangSmith, so its cost is paid on every single span.
"""

import uuid
from datetime import datetime, timezone

import pytest

from langsmith._internal._serde import _serialize_json, dumps_json
from tests.benchmarks._payloads import (
    DeeplyNestedModel,
    DeeplyNestedModelV1,
    PlainClass,
    create_json_with_large_array,
    create_json_with_large_strings,
    create_nested_instance,
)


@pytest.mark.parametrize("length", [100, 1_000])
def test_dumps_json_large_array(benchmark, length):
    payload = {"input": create_json_with_large_array(length)}
    benchmark(dumps_json, payload)


def test_dumps_json_large_strings(benchmark):
    payload = {"input": create_json_with_large_strings(50_000)}
    benchmark(dumps_json, payload)


def test_dumps_json_nested_dataclass(benchmark):
    payload = {"input": create_nested_instance(20, 20)}
    benchmark(dumps_json, payload)


def test_dumps_json_nested_pydantic(benchmark):
    payload = {
        "input": create_nested_instance(20, 20, branch_constructor=DeeplyNestedModel)
    }
    benchmark(dumps_json, payload)


def test_dumps_json_nested_pydantic_v1(benchmark):
    payload = {
        "input": create_nested_instance(20, 20, branch_constructor=DeeplyNestedModelV1)
    }
    benchmark(dumps_json, payload)


def test_dumps_json_nested_plain_class(benchmark):
    """Objects with no serialization protocol fall back to the slowest path."""
    payload = {"input": create_nested_instance(20, 20, leaf_constructor=PlainClass)}
    benchmark(dumps_json, payload)


def test_dumps_json_non_str_keys(benchmark):
    """Non-str dict keys force the key-normalization fallback in `dumps_json`."""
    payload = {
        "input": {
            (i, i + 1): {datetime.now(timezone.utc): uuid.uuid4()} for i in range(500)
        }
    }
    benchmark(dumps_json, payload)


def test_serialize_json_pydantic_model(benchmark):
    """The `default=` hook itself, isolated from orjson's own traversal."""
    model = DeeplyNestedModel()
    benchmark(_serialize_json, model)
