"""Unit tests for the shared ls_agent_type util."""

from types import SimpleNamespace

from langsmith._internal._ls_agent_type import (
    LS_AGENT_TYPES,
    NARROWING_LS_AGENT_TYPES,
    resolve_default_ls_agent_type,
)


def test_resolves_root_when_no_parent_runtree():
    assert resolve_default_ls_agent_type(None) == "root"


def test_resolves_none_when_nested_under_parent():
    parent = SimpleNamespace(extra={"metadata": {}})
    assert resolve_default_ls_agent_type(parent) is None


def test_narrowing_ls_agent_types_shape():
    assert NARROWING_LS_AGENT_TYPES == frozenset(
        {"middleware", "subagent", "compaction"}
    )


def test_ls_agent_types_shape():
    assert LS_AGENT_TYPES == frozenset({"root", "middleware", "subagent", "compaction"})


def test_ls_agent_types_is_narrowing_plus_root():
    assert LS_AGENT_TYPES == NARROWING_LS_AGENT_TYPES | {"root"}
