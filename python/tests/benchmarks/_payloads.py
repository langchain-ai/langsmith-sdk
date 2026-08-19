"""Shared payload builders for the CodSpeed benchmarks.

The shapes here mirror what the SDK actually sees in production: run payloads
built out of nested dataclasses / pydantic models, long string blobs and wide
arrays of small dicts. They are deliberately dependency-free (no numpy) so the
benchmark suite stays cheap to install.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional
from unittest.mock import MagicMock

from pydantic import BaseModel, Field
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1 import Field as FieldV1


def _default_vals() -> dict:
    return {
        "some_val": "😈",
        "uuid_val": uuid.uuid4(),
        "datetime_val": datetime.now(timezone.utc),
        "list_val": [238928376271863487] * 5,
        "decimal_val": Decimal("3.14"),
        "set_val": {1, 2, 3},
        "tuple_val": (4, 5, 6),
        "bytes_val": b"hello world",
    }


@dataclass
class DeeplyNested:
    vals: dict = field(default_factory=_default_vals)


class DeeplyNestedModel(BaseModel):
    vals: dict = Field(default_factory=_default_vals)


class DeeplyNestedModelV1(BaseModelV1):
    vals: dict = FieldV1(default_factory=_default_vals)


class PlainClass:
    """A plain object with no serialization protocol, hitting the slow path."""

    def __init__(self) -> None:
        self.vals: dict = {}


def create_nested_instance(
    depth: int = 5,
    width: int = 5,
    branch_constructor: Optional[Callable] = DeeplyNested,
    leaf_constructor: Optional[Callable] = None,
) -> DeeplyNested:
    """Build a `depth` x `width` tree of nested objects."""
    top_level = DeeplyNested()
    current_level = top_level
    root_constructor = leaf_constructor or DeeplyNested
    next_level: Any = None
    for i in range(depth):
        for j in range(width):
            key = f"key_{i}_{j}"
            if i < depth - 1:
                value = branch_constructor()  # type: ignore[misc]
                current_level.vals[key] = value
                if j == 0:
                    next_level = value
            else:
                current_level.vals[key] = root_constructor()

        if i < depth - 1:
            current_level = next_level
    return top_level


def create_json_with_large_array(length: int) -> dict:
    """A wide payload: many small homogeneous dicts."""
    return {
        "name": "Huge JSON",
        "description": "A large JSON object used for benchmarking.",
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


def create_json_with_large_strings(length: int) -> dict:
    """A payload dominated by a handful of very long strings."""
    large_string = "a" * length
    return {
        "name": "Huge JSON",
        "description": "A large JSON object used for benchmarking.",
        "key1": large_string,
        "key2": large_string,
        "key3": large_string,
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Python Program",
            "version": 1.0,
        },
    }


def create_run_payload(json_size: int = 100) -> dict:
    """A realistic `create_run` payload."""
    return {
        "name": "Run Name",
        "id": str(uuid.uuid4()),
        "run_type": "chain",
        "inputs": create_json_with_large_array(json_size),
        "outputs": create_json_with_large_array(json_size),
        "extra": {"extra_data": "value"},
        "trace_id": str(uuid.uuid4()),
        "dotted_order": "1.1",
        "tags": ["tag1", "tag2"],
        "session_name": "Session Name",
    }


def mock_session() -> MagicMock:
    """A `requests.Session` stand-in that accepts every request."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 202
    response.text = "Accepted"
    response.json.return_value = {"status": "success"}
    session.request.return_value = response
    return session
