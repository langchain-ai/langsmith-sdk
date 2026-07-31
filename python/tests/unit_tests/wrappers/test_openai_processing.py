"""Unit tests for OpenAI wrapper processing functions."""

from types import SimpleNamespace

import pytest

from langsmith.wrappers._openai import (
    _infer_invocation_params,
    _resolve_default_ls_agent_type,
    _traceable_kwargs_with_ls_agent_type,
)


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


def test_infer_invocation_params_carries_per_call_ls_agent_type():
    """Per-call metadata.ls_agent_type flows through invocation params."""
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {"model": "gpt-4o-mini", "metadata": {"ls_agent_type": "middleware"}},
    )
    assert result["ls_agent_type"] == "middleware"


def test_infer_invocation_params_does_not_stamp_ls_agent_type_by_default():
    """Absent per-call metadata means no ls_agent_type in invocation params.

    The default is stamped at the wrapper-config layer via
    ``_traceable_kwargs_with_ls_agent_type`` so wrapper-level user metadata is
    preserved through ``traceable``'s merge order.
    """
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert "ls_agent_type" not in result


def test_resolve_default_ls_agent_type_root_when_no_parent(monkeypatch):
    from langsmith import run_helpers

    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    assert _resolve_default_ls_agent_type() == "root"


@pytest.mark.parametrize("parent_tag", ["middleware", "subagent", "compaction"])
def test_resolve_default_ls_agent_type_inherits_narrowing_parent(
    monkeypatch, parent_tag
):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": parent_tag}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    assert _resolve_default_ls_agent_type() == parent_tag


def test_resolve_default_ls_agent_type_root_when_parent_untagged(monkeypatch):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    assert _resolve_default_ls_agent_type() == "root"


def test_resolve_default_ls_agent_type_root_when_parent_tag_is_root(monkeypatch):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": "root"}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    assert _resolve_default_ls_agent_type() == "root"


def test_traceable_kwargs_stamps_default_when_metadata_missing(monkeypatch):
    from langsmith import run_helpers

    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type({})
    assert result["metadata"]["ls_agent_type"] == "root"


@pytest.mark.parametrize(
    "wrapper_tag", ["root", "subagent", "middleware", "compaction"]
)
def test_traceable_kwargs_preserves_wrapper_supplied_tag(monkeypatch, wrapper_tag):
    """tracing_extra['metadata']['ls_agent_type'] must not be clobbered.

    Regression guard: earlier versions stamped ls_agent_type via
    ``_invocation_params_fn``, which merges after wrapper metadata inside
    ``traceable`` and silently overwrote wrapper-supplied policy.
    """
    from langsmith import run_helpers

    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type(
        {"metadata": {"ls_agent_type": wrapper_tag}}
    )
    assert result["metadata"]["ls_agent_type"] == wrapper_tag


def test_traceable_kwargs_does_not_mutate_input(monkeypatch):
    from langsmith import run_helpers

    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    original: dict = {"metadata": {"custom": "value"}}
    original_metadata = original["metadata"]
    _traceable_kwargs_with_ls_agent_type(original)
    assert original == {"metadata": {"custom": "value"}}
    assert original["metadata"] is original_metadata


def test_traceable_kwargs_inherits_parent_narrowing_tag(monkeypatch):
    from langsmith import run_helpers

    parent = SimpleNamespace(extra={"metadata": {"ls_agent_type": "middleware"}})
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: parent)
    result = _traceable_kwargs_with_ls_agent_type({})
    assert result["metadata"]["ls_agent_type"] == "middleware"
