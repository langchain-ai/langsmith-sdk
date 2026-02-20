"""Unit tests for Claude Agent SDK hooks."""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _client_managed_runs,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
)
from langsmith.run_trees import RunTree

ERROR_MSG = "Exit code 1\ncat: /nonexistent: No such file or directory"


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset global hook state between tests."""
    _active_tool_runs.clear()
    _client_managed_runs.clear()
    yield
    _active_tool_runs.clear()
    _client_managed_runs.clear()


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
        asyncio.get_event_loop().run_until_complete(
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

        asyncio.get_event_loop().run_until_complete(
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
        asyncio.get_event_loop().run_until_complete(
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

        asyncio.get_event_loop().run_until_complete(
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
    def test_injects_all_three_hooks(self):
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

        for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            assert event in options.hooks
            assert len(options.hooks[event]) == 1
