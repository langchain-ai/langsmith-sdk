"""Unit tests for langsmith.beta._self_report."""

import uuid
import warnings
from collections.abc import Iterator
from unittest import mock

import pytest

import langsmith as ls
from langsmith.beta import _self_report
from langsmith.beta._self_report import (
    DEFAULT_SELF_REPORT_CATEGORIES,
    SELF_REPORT_FEEDBACK_KEY,
    self_report,
    self_report_tool,
)


@pytest.fixture(autouse=True)
def _quiet_beta_warning() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.simplefilter(
            "ignore", ls._internal._beta_decorator.LangSmithBetaWarning
        )
        yield


@pytest.fixture
def client() -> mock.MagicMock:
    _self_report._project_ids.clear()
    client = mock.MagicMock(spec=ls.Client)
    client.read_project.return_value = mock.Mock(id=uuid.uuid4())
    return client


def _feedback_kwargs(client: mock.MagicMock) -> dict:
    client.create_feedback.assert_called_once()
    return client.create_feedback.call_args.kwargs


def test_schema_lists_default_categories() -> None:
    tool = self_report_tool()
    schema = tool.schema("anthropic")
    assert schema["name"] == "flag_for_review"
    assert schema["input_schema"]["properties"]["category"]["enum"] == [
        c["name"] for c in DEFAULT_SELF_REPORT_CATEGORIES
    ]
    for category in DEFAULT_SELF_REPORT_CATEGORIES:
        assert category["description"] in schema["description"]

    openai = tool.schema("openai")
    assert openai["type"] == "function"
    assert openai["function"]["parameters"] == schema["input_schema"]


def test_categories_replace_and_extra_categories_extend() -> None:
    custom = {"name": "policy_gap", "description": "The docs don't cover it."}
    replaced = self_report_tool(categories=[custom])
    assert replaced.input_schema["properties"]["category"]["enum"] == ["policy_gap"]

    extended = self_report_tool(extra_categories=[custom])
    enum = extended.input_schema["properties"]["category"]["enum"]
    assert enum[-1] == "policy_gap"
    assert len(enum) == len(DEFAULT_SELF_REPORT_CATEGORIES) + 1

    with pytest.raises(ValueError):
        self_report_tool(extra_categories=[DEFAULT_SELF_REPORT_CATEGORIES[0]])


def test_not_recorded_without_active_trace(client: mock.MagicMock) -> None:
    tool = self_report_tool(client=client)
    assert tool(category="tool_failing", reason="search kept failing").startswith(
        "Not recorded"
    )
    client.create_feedback.assert_not_called()


def test_report_from_traced_tool_goes_on_calling_step(
    client: mock.MagicMock,
) -> None:
    tool = self_report_tool()
    traced_tool = ls.traceable(run_type="tool", name="flag_for_review")(tool)
    ids = {}

    @ls.traceable(name="agent")
    def agent() -> str:
        return step()

    @ls.traceable(name="step")
    def step() -> str:
        current = ls.get_current_run_tree()
        ids["step"], ids["trace"] = current.id, current.trace_id
        ids["step_start"] = current.start_time
        return traced_tool(category="tool_failing", reason="search returned 503")

    with ls.tracing_context(enabled=True, client=client):
        assert agent() == "Recorded."

    kwargs = _feedback_kwargs(client)
    assert kwargs["run_id"] == ids["step"]
    assert kwargs["trace_id"] == ids["trace"]
    assert kwargs["start_time"] == ids["step_start"]
    assert kwargs["key"] == SELF_REPORT_FEEDBACK_KEY
    assert kwargs["value"] == "tool_failing"
    assert kwargs["comment"] == "search returned 503"
    assert kwargs["session_id"] == client.read_project.return_value.id


def test_report_from_untraced_tool_goes_on_current_run(
    client: mock.MagicMock,
) -> None:
    tool = self_report_tool()
    ids = {}

    @ls.traceable(name="agent")
    def agent() -> str:
        ids["agent"] = ls.get_current_run_tree().id
        return tool(category="missing_context", reason="no docs on refunds")

    with ls.tracing_context(enabled=True, client=client):
        assert agent() == "Recorded."
    assert _feedback_kwargs(client)["run_id"] == ids["agent"]


def test_langchain_tool_reports_on_calling_step(client: mock.MagicMock) -> None:
    pytest.importorskip("langchain_core")
    lc_tool = self_report_tool().as_langchain()
    ids = {}

    @ls.traceable(name="agent")
    def agent() -> str:
        ids["agent"] = ls.get_current_run_tree().id
        return lc_tool.invoke({"category": "task_failure", "reason": "gave up"})

    with ls.tracing_context(enabled=True, client=client):
        assert agent() == "Recorded."
    assert _feedback_kwargs(client)["run_id"] == ids["agent"]


def test_unknown_category_is_rejected(client: mock.MagicMock) -> None:
    tool = self_report_tool()

    @ls.traceable
    def agent() -> str:
        return tool(category="made_up", reason="something")

    with ls.tracing_context(enabled=True, client=client):
        result = agent()
    assert result.startswith("Not recorded: unknown category")
    client.create_feedback.assert_not_called()


def test_new_categories_when_allowed(client: mock.MagicMock) -> None:
    tool = self_report_tool(allow_new_categories=True)
    assert "enum" not in tool.input_schema["properties"]["category"]

    @ls.traceable
    def agent() -> str:
        return tool(category="Rate Limited!", reason="429 from the search API")

    with ls.tracing_context(enabled=True, client=client):
        assert agent() == "Recorded."
    kwargs = _feedback_kwargs(client)
    assert kwargs["value"] == "rate_limited"
    assert kwargs["source_info"] == {"new_category": True}


def test_max_per_trace(client: mock.MagicMock) -> None:
    tool = self_report_tool(max_per_trace=2)

    @ls.traceable
    def agent() -> list[str]:
        return [tool(category="task_failure", reason=str(i)) for i in range(3)]

    with ls.tracing_context(enabled=True, client=client):
        results = agent()
    assert results[:2] == ["Recorded.", "Recorded."]
    assert results[2].startswith("Not recorded")
    assert client.create_feedback.call_count == 2


def test_failed_write_does_not_raise(client: mock.MagicMock) -> None:
    client.create_feedback.side_effect = RuntimeError("boom")
    tool = self_report_tool()

    @ls.traceable
    def agent() -> str:
        return tool(category="task_failure", reason="gave up")

    with ls.tracing_context(enabled=True, client=client):
        assert agent().startswith("Not recorded")


def test_failed_project_lookup_is_retried(client: mock.MagicMock) -> None:
    project_id = uuid.uuid4()
    client.read_project.side_effect = [
        ls.utils.LangSmithNotFoundError("not yet"),
        mock.Mock(id=project_id),
    ]
    tool = self_report_tool()

    @ls.traceable
    def agent() -> None:
        tool(category="task_failure", reason="first")
        tool(category="task_failure", reason="second")

    with ls.tracing_context(enabled=True, client=client):
        agent()
    first, second = client.create_feedback.call_args_list
    assert "session_id" not in first.kwargs
    assert second.kwargs["session_id"] == project_id


def test_self_report_from_code(client: mock.MagicMock) -> None:
    ids = {}

    @ls.traceable(name="search")
    def search() -> bool:
        ids["search"] = ls.get_current_run_tree().id
        return self_report("tool_failing", "503 on three calls in a row")

    with ls.tracing_context(enabled=True, client=client):
        assert search() is True
    kwargs = _feedback_kwargs(client)
    assert kwargs["run_id"] == ids["search"]
    assert kwargs["value"] == "tool_failing"


def test_self_report_without_trace(client: mock.MagicMock) -> None:
    assert self_report("tool_failing", "no trace", client=client) is False
    client.create_feedback.assert_not_called()
