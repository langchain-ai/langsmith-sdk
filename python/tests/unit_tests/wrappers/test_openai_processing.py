"""Unit tests for OpenAI wrapper processing functions."""

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
