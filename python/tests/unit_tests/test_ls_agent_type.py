"""Unit tests for the shared ls_agent_type util."""

from types import SimpleNamespace

from langsmith._internal._ls_agent_type import (
    NON_ROOT_LS_AGENT_TYPES,
    apply_default_ls_agent_type,
    resolve_default_ls_agent_type,
)


def test_non_root_ls_agent_types_shape():
    assert NON_ROOT_LS_AGENT_TYPES == frozenset(
        {"middleware", "subagent", "compaction"}
    )


def test_resolves_root_when_no_parent_runtree():
    assert resolve_default_ls_agent_type(None) == "root"


def test_resolves_none_when_nested_under_parent():
    parent = SimpleNamespace(extra={"metadata": {}})
    assert resolve_default_ls_agent_type(parent) is None


def test_apply_default_stamps_root_when_no_parent_and_key_absent():
    metadata: dict = {}
    apply_default_ls_agent_type(metadata, None)
    assert metadata == {"ls_agent_type": "root"}


def test_apply_default_no_op_when_nested_and_key_absent():
    metadata: dict = {}
    parent = SimpleNamespace(extra={"metadata": {}})
    apply_default_ls_agent_type(metadata, parent)
    assert metadata == {}


def test_apply_default_preserves_user_supplied_value():
    metadata = {"ls_agent_type": "middleware"}
    apply_default_ls_agent_type(metadata, None)
    assert metadata == {"ls_agent_type": "middleware"}


def test_apply_default_preserves_none_opt_out():
    metadata = {"ls_agent_type": None}
    apply_default_ls_agent_type(metadata, None)
    assert metadata == {"ls_agent_type": None}
