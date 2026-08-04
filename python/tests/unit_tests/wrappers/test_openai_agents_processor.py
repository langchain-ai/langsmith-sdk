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
    return SimpleNamespace(
        name=name,
        trace_id=trace_id,
        metadata=metadata,
        export=lambda: {},
    )


def _run_trace_start(trace_metadata, processor_metadata=None, has_parent_runtree=True):
    """Fire on_trace_start and return the resulting run_extra.metadata."""
    client = mock.MagicMock(spec=Client)
    processor = OpenAIAgentsTracingProcessor(client=client, metadata=processor_metadata)
    trace = _fake_trace(metadata=trace_metadata)

    if has_parent_runtree:
        fake_parent = mock.MagicMock()
        fake_parent.create_child.return_value = mock.MagicMock()
        parent_return = fake_parent
    else:
        parent_return = None

    with mock.patch(
        "langsmith.integrations.openai_agents_sdk._openai_agents.get_current_run_tree",
        return_value=parent_return,
    ):
        processor.on_trace_start(trace)

    if has_parent_runtree:
        call = parent_return.create_child.call_args
        return call.kwargs["extra"]["metadata"]
    stored = next(iter(processor._runs.values()))
    return stored.extra["metadata"]


# ---------------------------------------------------------------------------
# on_trace_start
# ---------------------------------------------------------------------------


def test_stamps_default_root_when_no_parent_runtree():
    meta = _run_trace_start(trace_metadata=None, has_parent_runtree=False)
    assert meta["ls_agent_type"] == "root"


def test_no_default_stamp_when_nested_under_parent_runtree():
    meta = _run_trace_start(trace_metadata=None, has_parent_runtree=True)
    assert "ls_agent_type" not in meta


@pytest.mark.parametrize("user_tag", ["root", "middleware", "subagent", "compaction"])
def test_preserves_user_supplied_ls_agent_type(user_tag):
    meta = _run_trace_start(trace_metadata={"ls_agent_type": user_tag})
    assert meta["ls_agent_type"] == user_tag


def test_none_opt_out_at_trace_start_preserves_null():
    meta = _run_trace_start(trace_metadata={"ls_agent_type": None})
    assert meta["ls_agent_type"] is None


def test_trace_end_matches_trace_start_precedence():
    from unittest import mock as _mock

    from langsmith import Client
    from langsmith.integrations.openai_agents_sdk import (
        OpenAIAgentsTracingProcessor,
    )

    client = _mock.MagicMock(spec=Client)
    processor = OpenAIAgentsTracingProcessor(
        client=client, metadata={"ls_agent_type": "root"}
    )
    run = _mock.MagicMock()
    run.extra = {"metadata": {}}
    processor._runs["trace-1"] = run
    processor._last_response_outputs["trace-1"] = {}

    trace = SimpleNamespace(
        trace_id="trace-1",
        name="Agent workflow",
        metadata={"ls_agent_type": "middleware"},
        export=lambda: {"metadata": {"ls_agent_type": "middleware"}},
    )
    processor.on_trace_end(trace)
    assert run.extra["metadata"]["ls_agent_type"] == "middleware"


def test_preserves_other_user_trace_metadata():
    meta = _run_trace_start(
        trace_metadata={"middleware_name": "entry_guardrail", "phase": "entry"}
    )
    assert meta["middleware_name"] == "entry_guardrail"
    assert meta["phase"] == "entry"


def test_trace_metadata_wins_over_processor_metadata():
    meta = _run_trace_start(
        trace_metadata={"env": "prod"},
        processor_metadata={"env": "test"},
    )
    assert meta["env"] == "prod"


# ---------------------------------------------------------------------------
# Subagent structural detection (agent-as-tool)
# ---------------------------------------------------------------------------


def _run_subagent_stamp(existing_tag):
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
    return child_run.extra["metadata"].get("ls_agent_type")


def test_subagent_stamps_when_child_untagged():
    assert _run_subagent_stamp(None) == "subagent"


def test_subagent_overrides_inherited_root():
    # Structural detection overrides propagated root at agent-as-tool spans.
    assert _run_subagent_stamp("root") == "subagent"


@pytest.mark.parametrize("narrowing_tag", ["middleware", "compaction"])
def test_subagent_preserves_user_narrowing_tag(narrowing_tag):
    assert _run_subagent_stamp(narrowing_tag) == narrowing_tag


def test_subagent_preserves_existing_subagent_tag():
    assert _run_subagent_stamp("subagent") == "subagent"
