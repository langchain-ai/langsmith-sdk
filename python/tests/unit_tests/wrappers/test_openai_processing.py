"""Unit tests for OpenAI wrapper processing functions."""

from types import SimpleNamespace

import pytest

from langsmith import run_helpers
from langsmith.anonymizer import SECRET_PLACEHOLDER
from langsmith.wrappers._openai import (
    _infer_invocation_params,
    _process_inputs,
    _traceable_kwargs_with_ls_agent_type,
)

# ---------------------------------------------------------------------------
# _infer_invocation_params
# ---------------------------------------------------------------------------


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


def test_infer_invocation_params_no_longer_stamps_ls_agent_type():
    result = _infer_invocation_params(
        "chat", "openai", {}, False, {"model": "gpt-4o-mini"}
    )
    assert "ls_agent_type" not in result


def test_per_call_kwargs_metadata_ls_agent_type_flows_through():
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {"model": "gpt-4o-mini", "metadata": {"ls_agent_type": "middleware"}},
    )
    assert result["ls_agent_type"] == "middleware"


# ---------------------------------------------------------------------------
# _traceable_kwargs_with_ls_agent_type
# ---------------------------------------------------------------------------


def test_traceable_kwargs_stamps_root_at_top_level(monkeypatch):
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type({})
    assert result["metadata"]["ls_agent_type"] == "root"


@pytest.mark.parametrize(
    "wrapper_tag", ["root", "middleware", "subagent", "compaction"]
)
def test_traceable_kwargs_preserves_user_supplied_tag(monkeypatch, wrapper_tag):
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type(
        {"metadata": {"ls_agent_type": wrapper_tag}}
    )
    assert result["metadata"]["ls_agent_type"] == wrapper_tag


def test_traceable_kwargs_preserves_none_opt_out(monkeypatch):
    """None passes through so traceable's .update() sets ls_agent_type=None on
    the run, overriding any propagated parent tag."""
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type({"metadata": {"ls_agent_type": None}})
    assert result["metadata"]["ls_agent_type"] is None


def test_traceable_kwargs_does_not_mutate_input(monkeypatch):
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    original: dict = {"metadata": {"custom": "value"}}
    original_metadata = original["metadata"]
    _traceable_kwargs_with_ls_agent_type(original)
    assert original == {"metadata": {"custom": "value"}}
    assert original["metadata"] is original_metadata


def test_traceable_kwargs_preserves_other_user_metadata(monkeypatch):
    monkeypatch.setattr(run_helpers, "get_current_run_tree", lambda: None)
    result = _traceable_kwargs_with_ls_agent_type(
        {"metadata": {"customer_id": "cust-123"}}
    )
    assert result["metadata"]["customer_id"] == "cust-123"
    assert result["metadata"]["ls_agent_type"] == "root"


# ---------------------------------------------------------------------------
# End-to-end (helper decision + traceable outer_metadata merge)
# ---------------------------------------------------------------------------


def _simulate_child_metadata(parent_metadata, wrapper_metadata=None):
    from langsmith._internal import _context

    parent_runtree = SimpleNamespace(extra={"metadata": parent_metadata})
    token = _context._METADATA.set(dict(parent_metadata))
    prev_get = run_helpers.get_current_run_tree
    run_helpers.get_current_run_tree = lambda: parent_runtree
    try:
        helper_out = _traceable_kwargs_with_ls_agent_type(wrapper_metadata or {})
        child_metadata = {**(_context._METADATA.get() or {})}
        child_metadata.update(helper_out.get("metadata") or {})
        return {"helper_output": helper_out, "child_metadata": child_metadata}
    finally:
        _context._METADATA.reset(token)
        run_helpers.get_current_run_tree = prev_get


@pytest.mark.parametrize("parent_tag", ["root", "middleware", "subagent", "compaction"])
def test_propagation_carries_parent_tag_to_nested_llm_run(parent_tag):
    result = _simulate_child_metadata({"ls_agent_type": parent_tag})
    assert "ls_agent_type" not in result["helper_output"]["metadata"]
    assert result["child_metadata"].get("ls_agent_type") == parent_tag


def test_no_tag_on_nested_when_parent_untagged():
    result = _simulate_child_metadata({})
    assert "ls_agent_type" not in result["helper_output"]["metadata"]
    assert "ls_agent_type" not in result["child_metadata"]


def test_user_wrapper_tag_overrides_propagation():
    result = _simulate_child_metadata(
        parent_metadata={"ls_agent_type": "root"},
        wrapper_metadata={"metadata": {"ls_agent_type": "middleware"}},
    )
    assert result["child_metadata"].get("ls_agent_type") == "middleware"


def test_nested_none_opt_out_overrides_propagated_tag():
    """User's None at wrapper level overrides a propagated middleware tag,
    landing ls_agent_type=None on the child (backend treats null as no-tag).
    """
    result = _simulate_child_metadata(
        parent_metadata={"ls_agent_type": "middleware"},
        wrapper_metadata={"metadata": {"ls_agent_type": None}},
    )
    assert "ls_agent_type" in result["child_metadata"]
    assert result["child_metadata"]["ls_agent_type"] is None


# ---------------------------------------------------------------------------
# credential masking
# ---------------------------------------------------------------------------

FAKE_TOKEN = "fake-token-for-tests-only"


def _mcp_tools(**extra) -> list:
    return [
        {
            "type": "mcp",
            "server_label": "example",
            "server_url": "https://mcp.example.com/sse",
            "authorization": FAKE_TOKEN,
            "headers": {"Authorization": f"Bearer {FAKE_TOKEN}"},
            **extra,
        }
    ]


class TestRedactHostedMCPTools:
    """Responses API `tools` may carry a bearer credential and auth headers."""

    def test_process_inputs_masks_authorization_and_headers(self) -> None:
        tool = _process_inputs({"model": "gpt-5", "tools": _mcp_tools()})["tools"][0]

        assert tool["authorization"] == SECRET_PLACEHOLDER
        assert tool["headers"] == SECRET_PLACEHOLDER
        assert tool["type"] == "mcp"
        assert tool["server_label"] == "example"
        assert tool["server_url"] == "https://mcp.example.com/sse"

    def test_infer_invocation_params_never_carries_the_token(self) -> None:
        """Guards against building invocation params from the raw kwargs."""
        params = _infer_invocation_params(
            "chat", "openai", {}, True, {"model": "gpt-5", "tools": _mcp_tools()}
        )

        assert FAKE_TOKEN not in str(params)

    def test_does_not_mutate_the_callers_tools(self) -> None:
        """The same objects are sent to OpenAI, so they keep the real token."""
        tools = _mcp_tools()
        kwargs = {"model": "gpt-5", "tools": tools}

        _process_inputs(kwargs)
        _infer_invocation_params("chat", "openai", {}, True, kwargs)

        assert tools[0]["authorization"] == FAKE_TOKEN
        assert tools[0]["headers"] == {"Authorization": f"Bearer {FAKE_TOKEN}"}

    def test_masks_fields_that_are_not_explicitly_allowed(self) -> None:
        """A credential field added to the API later is masked by default."""
        tool = _process_inputs({"tools": _mcp_tools(future_secret="s3cret")})["tools"][
            0
        ]

        assert tool["future_secret"] == SECRET_PLACEHOLDER

    def test_function_tools_keep_their_schema(self) -> None:
        tools = [
            {
                "type": "function",
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            }
        ]

        assert _process_inputs({"tools": tools})["tools"] == tools

    @pytest.mark.parametrize(
        ("tools", "expected"),
        [
            ("not-a-list", "not-a-list"),
            ([None], [None]),
            ([["nested"]], [["nested"]]),
            ([], []),
            ((), []),  # tuples are normalized to lists
        ],
    )
    def test_tolerates_unexpected_shapes(self, tools, expected) -> None:
        assert _process_inputs({"tools": tools})["tools"] == expected


class TestRedactTransportOverrides:
    """`extra_*` are credentials by construction; only key names survive."""

    @pytest.mark.parametrize("key", ["extra_headers", "extra_body", "extra_query"])
    def test_masks_values_but_keeps_key_names(self, key) -> None:
        result = _process_inputs({key: {"Authorization": f"Bearer {FAKE_TOKEN}"}})

        assert result[key] == {"Authorization": SECRET_PLACEHOLDER}

    def test_does_not_mutate_the_callers_headers(self) -> None:
        headers = {"Authorization": f"Bearer {FAKE_TOKEN}"}
        kwargs = {"model": "gpt-5", "extra_headers": headers}

        _process_inputs(kwargs)

        assert headers["Authorization"] == f"Bearer {FAKE_TOKEN}"
        assert kwargs["extra_headers"] is headers

    def test_unset_overrides_are_left_alone(self) -> None:
        assert _process_inputs({"model": "gpt-5"}) == {"model": "gpt-5"}
