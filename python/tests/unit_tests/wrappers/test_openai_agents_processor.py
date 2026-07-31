"""Unit tests for OpenAIAgentsTracingProcessor metadata stamping."""

from types import SimpleNamespace
from unittest import mock

import pytest

pytest.importorskip("agents")

from agents import tracing  # noqa: E402

from langsmith import Client  # noqa: E402
from langsmith.integrations.openai_agents_sdk import (  # noqa: E402
    OpenAIAgentsTracingProcessor,
)


def _fake_trace(metadata=None, name="workflow", trace_id="trace-1"):
    trace = SimpleNamespace(
        name=name,
        trace_id=trace_id,
        metadata=metadata,
        export=lambda: {},
    )
    return trace


def _capture_run_extra(processor):
    """Run on_trace_start against a fake trace and return the resulting extra."""
    captured = {}

    def fake_create_child(**kwargs):
        captured.update(kwargs)
        run = mock.MagicMock()
        run.id = "run-id"
        return run

    with mock.patch(
        "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
        return_value=SimpleNamespace(create_child=fake_create_child),
    ):
        return captured


def _run_trace_start(trace_metadata, processor_metadata=None):
    client = mock.MagicMock(spec=Client)
    processor = OpenAIAgentsTracingProcessor(client=client, metadata=processor_metadata)
    trace = _fake_trace(metadata=trace_metadata)

    fake_parent = mock.MagicMock()
    fake_parent.create_child.return_value = mock.MagicMock()
    with mock.patch(
        "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
        return_value=fake_parent,
    ):
        processor.on_trace_start(trace)

    call = fake_parent.create_child.call_args
    return call.kwargs["extra"]["metadata"]


def test_on_trace_start_defaults_to_root_when_no_user_tag():
    meta = _run_trace_start(trace_metadata=None)
    assert meta["ls_agent_type"] == "root"
    assert meta["ls_integration"] == "openai-agents-sdk"


@pytest.mark.parametrize("user_tag", ["middleware", "subagent", "compaction", "root"])
def test_on_trace_start_preserves_user_supplied_ls_agent_type(user_tag):
    meta = _run_trace_start(trace_metadata={"ls_agent_type": user_tag})
    assert meta["ls_agent_type"] == user_tag


def test_on_trace_start_force_sets_ls_integration_even_if_user_overrides():
    meta = _run_trace_start(
        trace_metadata={
            "ls_integration": "user-override",
            "ls_agent_type": "middleware",
        }
    )
    assert meta["ls_integration"] == "openai-agents-sdk"
    assert meta["ls_agent_type"] == "middleware"


def test_on_trace_start_preserves_other_user_trace_metadata():
    meta = _run_trace_start(
        trace_metadata={"middleware_name": "entry_guardrail", "phase": "entry"}
    )
    assert meta["middleware_name"] == "entry_guardrail"
    assert meta["phase"] == "entry"
    assert meta["ls_agent_type"] == "root"


def test_on_trace_start_processor_metadata_still_applied():
    meta = _run_trace_start(trace_metadata=None, processor_metadata={"env": "test"})
    assert meta["env"] == "test"
    assert meta["ls_agent_type"] == "root"


def test_on_trace_start_trace_metadata_wins_over_processor_metadata():
    meta = _run_trace_start(
        trace_metadata={"env": "prod"},
        processor_metadata={"env": "test"},
    )
    assert meta["env"] == "prod"


def _run_subagent_stamp(existing_tag):
    """Fire the subagent-detection path with a pre-existing tag on child_run."""
    client = mock.MagicMock(spec=Client)
    processor = OpenAIAgentsTracingProcessor(client=client)

    parent_span_id = "parent-fn"
    child_span_id = "child-agent"
    processor._span_data_types[parent_span_id] = tracing.FunctionSpanData

    parent_run = mock.MagicMock()
    parent_run.id = "parent-run"
    processor._runs[parent_span_id] = parent_run

    child_run = mock.MagicMock()
    initial_meta = {"ls_agent_type": existing_tag} if existing_tag is not None else {}
    child_run.extra = {"metadata": initial_meta}
    parent_run.create_child.return_value = child_run

    child_span = SimpleNamespace(
        span_id=child_span_id,
        parent_id=parent_span_id,
        trace_id="trace-1",
        started_at=None,
        span_data=mock.MagicMock(spec=tracing.AgentSpanData),
    )
    child_span.span_data.export = mock.MagicMock(return_value={})
    child_span.span_data.name = "Some Subagent"

    processor.on_span_start(child_span)
    return child_run.extra["metadata"]["ls_agent_type"]


@pytest.mark.parametrize("existing_tag", ["middleware", "compaction"])
def test_subagent_stamp_preserves_user_narrowing_tags(existing_tag):
    """User-supplied middleware/compaction beats structural subagent detection."""
    assert _run_subagent_stamp(existing_tag) == existing_tag


@pytest.mark.parametrize("existing_tag", [None, "root", "subagent"])
def test_subagent_stamp_applies_structural_detection(existing_tag):
    """Missing tag, inherited root, or already-subagent all resolve to subagent."""
    assert _run_subagent_stamp(existing_tag) == "subagent"


def _run_trace_end(trace_metadata):
    """Fire on_trace_end and return the run's final metadata."""
    client = mock.MagicMock(spec=Client)
    processor = OpenAIAgentsTracingProcessor(client=client)

    run = mock.MagicMock()
    run.extra = {"metadata": {}}
    processor._runs["trace-1"] = run
    processor._last_response_outputs["trace-1"] = {}

    trace = SimpleNamespace(
        trace_id="trace-1",
        name="Agent workflow",
        metadata=trace_metadata,
        export=lambda: {"metadata": trace_metadata} if trace_metadata else {},
    )
    processor.on_trace_end(trace)
    return run.extra["metadata"]


def test_on_trace_end_force_sets_ls_integration():
    meta = _run_trace_end({"ls_integration": "user-override"})
    assert meta["ls_integration"] == "openai-agents-sdk"


def test_on_trace_end_preserves_other_user_metadata():
    meta = _run_trace_end({"middleware_name": "exit_guardrail"})
    assert meta["middleware_name"] == "exit_guardrail"
    assert meta["ls_integration"] == "openai-agents-sdk"
