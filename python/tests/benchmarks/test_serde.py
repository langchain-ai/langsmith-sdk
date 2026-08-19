"""Benchmarks for the JSON serialization layer (`langsmith._internal._serde`).

Every traced run goes through `dumps_json`, so its cost directly shows up in the
tracing hot path. The payload shapes below mirror the ones used by the existing
`bench/` suite: deeply nested dataclasses, Pydantic v1/v2 models and plain
Python objects (which take the slowest, reflection based, path).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1 import Field as FieldV1

from langsmith._internal._serde import dumps_json


def _leaf_values() -> Dict[str, Any]:
    return {
        "some_val": "😈",
        "uuid_val": uuid4(),
        "datetime_val": datetime.now(timezone.utc),
        "list_val": [238928376271863487] * 5,
        "decimal_val": Decimal("3.14"),
        "set_val": {1, 2, 3},
        "tuple_val": (4, 5, 6),
        "bytes_val": b"hello world",
    }


@dataclass
class NestedDataclass:
    vals: Dict[str, Any] = field(default_factory=_leaf_values)


class NestedModel(BaseModel):
    vals: Dict[str, Any] = Field(default_factory=_leaf_values)


class NestedModelV1(BaseModelV1):
    vals: Dict[str, Any] = FieldV1(default_factory=_leaf_values)


class NestedPlainObject:
    """A vanilla object: serialization has to fall back to `vars()`."""

    def __init__(self) -> None:
        self.vals: Dict[str, Any] = {}


def create_nested_instance(
    depth: int,
    width: int,
    branch_constructor: Optional[Callable] = NestedDataclass,
    leaf_constructor: Optional[Callable] = None,
) -> NestedDataclass:
    top_level = NestedDataclass()
    current_level = top_level
    root_constructor = leaf_constructor or NestedDataclass
    next_level = top_level
    for i in range(depth):
        for j in range(width):
            key = f"key_{i}_{j}"
            if i < depth - 1:
                value = branch_constructor()
                current_level.vals[key] = value
                if j == 0:
                    next_level = value
            else:
                current_level.vals[key] = root_constructor()
        if i < depth - 1:
            current_level = next_level
    return top_level


def _large_array_payload(length: int) -> Dict[str, Any]:
    return {
        "name": "Huge JSON",
        "description": "A large JSON object, similar to a real run payload.",
        "array": [
            {
                "index": i,
                "data": f"This is element number {i}",
                "nested": {"id": i, "value": f"Nested value for element {i}"},
            }
            for i in range(length)
        ],
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Python Program",
            "version": 1.0,
        },
    }


def _large_strings_payload(length: int) -> Dict[str, Any]:
    large_string = "a" * length
    return {
        "name": "Huge JSON",
        "key1": large_string,
        "key2": large_string,
        "key3": large_string,
        "metadata": {"created_at": "2024-10-22T19:00:00Z", "version": 1.0},
    }


@pytest.mark.benchmark
def test_dumps_json_nested_dataclass(benchmark):
    payload = create_nested_instance(20, 20)
    benchmark(lambda: dumps_json({"input": payload}))


@pytest.mark.benchmark
def test_dumps_json_nested_pydantic(benchmark):
    payload = create_nested_instance(20, 20, branch_constructor=NestedModel)
    benchmark(lambda: dumps_json({"input": payload}))


@pytest.mark.benchmark
def test_dumps_json_nested_pydantic_v1(benchmark):
    payload = create_nested_instance(20, 20, branch_constructor=NestedModelV1)
    benchmark(lambda: dumps_json({"input": payload}))


@pytest.mark.benchmark
def test_dumps_json_nested_plain_objects(benchmark):
    payload = create_nested_instance(
        20,
        20,
        branch_constructor=NestedPlainObject,
        leaf_constructor=NestedPlainObject,
    )
    benchmark(lambda: dumps_json({"input": payload}))


@pytest.mark.benchmark
def test_dumps_json_large_array(benchmark):
    payload = _large_array_payload(2_000)
    benchmark(lambda: dumps_json(payload))


@pytest.mark.benchmark
def test_dumps_json_large_strings(benchmark):
    payload = _large_strings_payload(100_000)
    benchmark(lambda: dumps_json(payload))


@pytest.mark.benchmark
def test_dumps_json_many_small_payloads(benchmark):
    payloads = [
        {
            "id": str(uuid4()),
            "messages": [
                {"role": "user", "content": f"hello {i}"},
                {"role": "assistant", "content": f"hi {i}"},
            ],
            "metadata": {"ls_model_name": "gpt-4o-mini", "iteration": i},
        }
        for i in range(500)
    ]

    def run() -> None:
        for payload in payloads:
            dumps_json(payload)

    benchmark(run)
