"""Unit tests for Claude Agent SDK hooks."""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _agent_to_tool_mapping,
    _ended_subagent_runs,
    _pending_agent_tools,
    _pending_subagent_traces,
    _subagent_runs,
    clear_active_tool_runs,
    get_subagent_run_by_tool_id,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
    subagent_start_hook,
    subagent_stop_hook,
)
from langsmith.run_trees import RunTree

ERROR_MSG = "Exit code 1\ncat: /nonexistent: No such file or directory"


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset global hook state between tests."""
    _active_tool_runs.clear()
    _subagent_runs.clear()
    _pending_agent_tools.clear()
    _agent_to_tool_mapping.clear()
    _ended_subagent_runs.clear()
    _pending_subagent_traces.clear()
    yield
    _active_tool_runs.clear()
    _subagent_runs.clear()
    _pending_agent_tools.clear()
    _agent_to_tool_mapping.clear()
    _ended_subagent_runs.clear()
    _pending_subagent_traces.clear()


def _make_parent_run() -> RunTree:
    """Create a detached RunTree suitable for parenting child runs."""
    return RunTree(name="test-parent", run_type="chain", client=MagicMock())


class TestToolUseSuccessFlow:
    """PreToolUse creates a child run; PostToolUse ends it with output."""

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        _tools.set_parent_run_tree(_make_parent_run())
        yield
        _tools.clear_parent_run_tree()

    def test_success_flow(self):
        asyncio.run(
            pre_tool_use_hook(
                {"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
                "tu_1",
                MagicMock(),
            )
        )

        assert "tu_1" in _active_tool_runs
        tool_run, _ = _active_tool_runs["tu_1"]
        assert tool_run.name == "Bash"
        assert tool_run.run_type == "tool"
        assert tool_run.inputs == {"input": {"command": "echo hi"}}

        asyncio.run(
            post_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_response": {"output": "hi", "is_error": False},
                },
                "tu_1",
                MagicMock(),
            )
        )

        assert "tu_1" not in _active_tool_runs
        assert tool_run.outputs == {"output": "hi", "is_error": False}
        assert tool_run.error is None


class TestToolUseFailureFlow:
    """PreToolUse creates a child run; PostToolUseFailure marks it as errored."""

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        _tools.set_parent_run_tree(_make_parent_run())
        yield
        _tools.clear_parent_run_tree()

    def test_failure_flow(self):
        asyncio.run(
            pre_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "cat /nonexistent"},
                },
                "tu_2",
                MagicMock(),
            )
        )

        tool_run, _ = _active_tool_runs["tu_2"]

        asyncio.run(
            post_tool_use_failure_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "cat /nonexistent"},
                    "error": ERROR_MSG,
                },
                "tu_2",
                MagicMock(),
            )
        )

        assert "tu_2" not in _active_tool_runs
        assert tool_run.error == ERROR_MSG
        assert tool_run.outputs == {"error": ERROR_MSG}


class TestInjectTracingHooks:
    def test_injects_all_hooks(self):
        from langsmith.integrations.claude_agent_sdk._client import (
            _inject_tracing_hooks,
        )

        options = MagicMock()
        options.hooks = None

        mock_module = MagicMock()
        sys.modules["claude_agent_sdk"] = mock_module
        try:
            _inject_tracing_hooks(options)
        finally:
            del sys.modules["claude_agent_sdk"]

        for event in (
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
            "SubagentStart",
            "SubagentStop",
        ):
            assert event in options.hooks
            assert len(options.hooks[event]) == 1


class TestSubagentFlow:
    """Test subagent start/stop hooks and tool nesting."""

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        _tools.set_parent_run_tree(_make_parent_run())
        yield
        _tools.clear_parent_run_tree()

    def test_subagent_nested_under_agent_tool(self):
        """Subagent run should be nested under the Agent tool run."""
        # PreToolUse for the Agent tool
        asyncio.run(
            pre_tool_use_hook(
                {"tool_name": "Agent", "tool_input": {"agent": "foo"}},
                "tool_1",
                MagicMock(),
            )
        )

        assert "tool_1" in _active_tool_runs
        agent_tool_run, _ = _active_tool_runs["tool_1"]
        assert agent_tool_run.name == "Agent"

        # The Agent tool_use_id should be pending
        assert "tool_1" in _pending_agent_tools

        # SubagentStart — note: SDK passes a different tool_use_id
        asyncio.run(
            subagent_start_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_internal_session_id",  # NOT tool_1
                MagicMock(),
            )
        )

        # Subagent run should exist and be nested under Agent tool
        assert "agent_123" in _subagent_runs
        subagent_run = _subagent_runs["agent_123"]
        assert subagent_run.name == "foo"
        assert subagent_run.run_type == "chain"
        assert subagent_run.parent_run_id == agent_tool_run.id

        # Inputs should come from the Agent tool's input
        assert subagent_run.inputs == {"agent": "foo"}

        # Mappings should be set
        assert _agent_to_tool_mapping["agent_123"] == "tool_1"
        assert get_subagent_run_by_tool_id("tool_1") == subagent_run

        # Pending should be consumed
        assert "tool_1" not in _pending_agent_tools

    def test_tool_inside_subagent_uses_subagent_as_parent(self):
        """Tools inside a subagent should use the subagent run as parent."""
        # Set up: Agent tool call + subagent start
        asyncio.run(
            pre_tool_use_hook(
                {"tool_name": "Agent", "tool_input": {"agent": "foo"}},
                "tool_1",
                MagicMock(),
            )
        )
        asyncio.run(
            subagent_start_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_session_id",
                MagicMock(),
            )
        )

        # Tool inside subagent — agent_id identifies the subagent
        asyncio.run(
            pre_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                    "agent_id": "agent_123",
                },
                "tool_2",
                MagicMock(),
            )
        )

        assert "tool_2" in _active_tool_runs
        tool_run, _ = _active_tool_runs["tool_2"]
        assert tool_run.name == "Bash"
        assert tool_run.parent_run_id == _subagent_runs["agent_123"].id

    def test_subagent_findable_after_stop(self):
        """Subagent run is still findable via tool_use_id after SubagentStop."""
        asyncio.run(
            pre_tool_use_hook(
                {"tool_name": "Agent", "tool_input": {}},
                "tool_1",
                MagicMock(),
            )
        )
        asyncio.run(
            subagent_start_hook(
                {"agent_id": "a1", "agent_type": "foo"},
                "sdk_1",
                MagicMock(),
            )
        )

        run = _subagent_runs["a1"]
        assert get_subagent_run_by_tool_id("tool_1") is run

        # After SubagentStop, the run is stashed but still findable
        asyncio.run(
            subagent_stop_hook(
                {"agent_id": "a1", "agent_type": "foo"},
                "sdk_1",
                MagicMock(),
            )
        )
        assert "a1" not in _subagent_runs
        assert get_subagent_run_by_tool_id("tool_1") is run

    def test_subagent_stop_and_post_tool_use_set_outputs(self):
        """SubagentStop + PostToolUse should set outputs on both runs."""
        # Agent tool call
        asyncio.run(
            pre_tool_use_hook(
                {"tool_name": "Agent", "tool_input": {"agent": "foo"}},
                "tool_1",
                MagicMock(),
            )
        )
        # Subagent start
        asyncio.run(
            subagent_start_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_session_id",
                MagicMock(),
            )
        )
        subagent_run = _subagent_runs["agent_123"]

        # Subagent stop — run should be stashed, not ended yet
        asyncio.run(
            subagent_stop_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_session_id",
                MagicMock(),
            )
        )

        assert "agent_123" not in _subagent_runs
        assert "tool_1" in _ended_subagent_runs
        assert _ended_subagent_runs["tool_1"] is subagent_run
        assert subagent_run.end_time is None

        # PostToolUse for Agent — sets outputs on subagent but doesn't end it
        asyncio.run(
            post_tool_use_hook(
                {
                    "tool_name": "Agent",
                    "tool_response": {"output": "bar"},
                },
                "tool_1",
                MagicMock(),
            )
        )

        # Agent tool run should be ended
        assert "tool_1" not in _active_tool_runs

        # Subagent outputs should be set but run not yet ended
        assert subagent_run.outputs == {"output": "bar"}
        assert subagent_run.end_time is None

        # Subagent can still be found for LLM nesting
        assert get_subagent_run_by_tool_id("tool_1") is subagent_run

        # clear_active_tool_runs finalises everything
        clear_active_tool_runs()
        assert subagent_run.end_time is not None
        assert len(_ended_subagent_runs) == 0
