"""Unit tests for OpenAI wrapper processing functions."""

from types import SimpleNamespace

import pytest

from langsmith.wrappers._openai import _infer_invocation_params


def test_infer_invocation_params_copies_request_metadata():
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {
            "model": "gpt-4o-mini",
            "metadata": {
                "customer_id": "customer-123",
                "environment": "test",
            },
        },
    )

    assert result["customer_id"] == "customer-123"
    assert result["environment"] == "test"
    assert "metadata" not in result["ls_invocation_params"]


def test_infer_invocation_params_protects_langsmith_metadata():
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {
            "model": "gpt-4o-mini",
            "metadata": {
                "ls_provider": "other",
                "ls_model_name": "other-model",
            },
        },
    )

    assert result["ls_provider"] == "openai"
    assert result["ls_model_name"] == "gpt-4o-mini"


@pytest.mark.parametrize("metadata", [None, "invalid", ["invalid"]])
def test_infer_invocation_params_ignores_non_mapping_metadata(metadata):
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {"model": "gpt-4o-mini", "metadata": metadata},
    )

    assert result["ls_provider"] == "openai"
    assert result["ls_model_name"] == "gpt-4o-mini"


def test_ls_agent_type_defaults_to_root_when_no_parent(monkeypatch):
    from langsmith import run_helpers

    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert result["ls_agent_type"] == "root"


@pytest.mark.parametrize("parent_tag", ["middleware", "subagent", "compaction"])
def test_ls_agent_type_inherits_narrowing_parent_tag(monkeypatch, parent_tag):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": parent_tag}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert result["ls_agent_type"] == parent_tag


def test_ls_agent_type_defaults_root_when_parent_untagged(monkeypatch):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert result["ls_agent_type"] == "root"


def test_ls_agent_type_defaults_root_when_parent_tag_is_root(monkeypatch):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": "root"}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert result["ls_agent_type"] == "root"


@pytest.mark.parametrize("user_tag", ["root", "subagent", "middleware", "compaction"])
def test_ls_agent_type_respects_user_supplied_per_call_tag(monkeypatch, user_tag):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": "middleware"}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {"model": "gpt-4o-mini", "metadata": {"ls_agent_type": user_tag}},
    )
    assert result["ls_agent_type"] == user_tag
