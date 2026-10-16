"""dumps_json must not raise RecursionError on cyclic or deeply nested structures.

Regression tests for https://github.com/langchain-ai/langsmith-sdk/issues/3393
"""

import json

import pytest

from langsmith._internal._serde import (
    _CYCLIC_PLACEHOLDER,
    _DEPTH_PLACEHOLDER,
    _break_cycles,
    dumps_json,
)


# ---------------------------------------------------------------------------
# _break_cycles unit tests
# ---------------------------------------------------------------------------


def test_break_cycles_dict_self_reference():
    d: dict = {}
    d["self"] = d
    result = _break_cycles(d)
    assert result == {"self": _CYCLIC_PLACEHOLDER}


def test_break_cycles_list_self_reference():
    lst: list = []
    lst.append(lst)
    result = _break_cycles(lst)
    assert result == [_CYCLIC_PLACEHOLDER]


def test_break_cycles_nested_cycle():
    a: dict = {}
    b: dict = {"parent": a}
    a["child"] = b
    result = _break_cycles(a)
    assert result["child"]["parent"] == _CYCLIC_PLACEHOLDER


def test_break_cycles_deep_nesting():
    # Build a chain of 100 nested dicts — well under _MAX_BREAK_DEPTH so it survives intact
    obj: dict = {}
    current = obj
    for _ in range(60):
        inner: dict = {}
        current["next"] = inner
        current = inner
    result = _break_cycles(obj)
    assert result is not obj  # a copy, not the original
    assert _DEPTH_PLACEHOLDER not in str(result)


def test_break_cycles_exceeds_depth_limit():
    # Build a chain deeper than _MAX_BREAK_DEPTH (64)
    obj: dict = {}
    current = obj
    for _ in range(70):
        inner: dict = {}
        current["next"] = inner
        current = inner
    result = _break_cycles(obj)
    assert _DEPTH_PLACEHOLDER in str(result)


def test_break_cycles_leaves_plain_values_intact():
    original = {"a": 1, "b": [2, 3], "c": "hello"}
    result = _break_cycles(original)
    assert result == original


def test_break_cycles_shared_reference_not_confused_with_cycle():
    # Sharing a reference is not a cycle — the same object appears in two places
    # but there is no back-edge.
    shared = {"x": 1}
    obj = {"first": shared, "second": shared}
    result = _break_cycles(obj)
    # shared is reached via two distinct paths; neither is a cycle
    assert result == obj


# ---------------------------------------------------------------------------
# dumps_json integration tests
# ---------------------------------------------------------------------------


def test_dumps_json_dict_cycle_does_not_raise():
    d: dict = {}
    d["self"] = d
    result = dumps_json({"cyclic": d})
    parsed = json.loads(result)
    assert parsed["cyclic"]["self"] == _CYCLIC_PLACEHOLDER


def test_dumps_json_list_cycle_does_not_raise():
    lst: list = []
    lst.append(lst)
    result = dumps_json({"cyclic": lst})
    parsed = json.loads(result)
    assert parsed["cyclic"][0] == _CYCLIC_PLACEHOLDER


def test_dumps_json_normal_data_unchanged():
    payload = {"messages": [{"role": "user", "content": "hello"}], "count": 42}
    assert json.loads(dumps_json(payload)) == payload


def test_dumps_json_deeply_nested_does_not_raise():
    # Build a non-cyclic dict chain deep enough to trigger RecursionError without
    # the fix (orjson serializes ~1 000 levels before raising).
    import sys

    depth = min(sys.getrecursionlimit() + 50, 1100)
    obj: dict = {}
    current = obj
    for _ in range(depth):
        inner: dict = {}
        current["next"] = inner
        current = inner
    # Must not raise — the depth limiter in _break_cycles replaces the tail
    result = dumps_json(obj)
    assert isinstance(result, bytes)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
