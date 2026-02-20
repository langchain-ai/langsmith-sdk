"""Unit tests for Claude Agent SDK hook handlers."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _client_managed_runs,
    clear_active_tool_runs,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
)


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset global hook state before each test."""
    _active_tool_runs.clear()
    _client_managed_runs.clear()
    yield
    _active_tool_runs.clear()
    _client_managed_runs.clear()


def _make_mock_run():
    run = MagicMock()
    run.create_child.return_value = MagicMock()
    run.create_child.return_value.post = MagicMock()
    run.create_child.return_value.end = MagicMock()
    run.create_child.return_value.patch = MagicMock()
    return run


# ---- PreToolUse ----


class TestPreToolUseHook:
    def test_skips_without_tool_use_id(self):
        result = asyncio.get_event_loop().run_until_complete(
            pre_tool_use_hook({"tool_name": "Bash"}, None, MagicMock())
        )
        assert result == {}
        assert len(_active_tool_runs) == 0

    def test_skips_client_managed_runs(self):
        _client_managed_runs["tu_123"] = MagicMock()
        result = asyncio.get_event_loop().run_until_complete(
            pre_tool_use_hook({"tool_name": "Bash"}, "tu_123", MagicMock())
        )
        assert result == {}
        assert "tu_123" not in _active_tool_runs

    @patch("langsmith.integrations.claude_agent_sdk._hooks.get_parent_run_tree")
    def test_creates_child_run(self, mock_parent):
        parent = _make_mock_run()
        mock_parent.return_value = parent

        result = asyncio.get_event_loop().run_until_complete(
            pre_tool_use_hook(
                {"tool_name": "Bash", "tool_input": {"command": "ls"}},
                "tu_456",
                MagicMock(),
            )
        )

        assert result == {}
        assert "tu_456" in _active_tool_runs
        parent.create_child.assert_called_once()
        call_kwargs = parent.create_child.call_args
        assert call_kwargs.kwargs["name"] == "Bash"
        assert call_kwargs.kwargs["run_type"] == "tool"
        assert call_kwargs.kwargs["inputs"] == {"input": {"command": "ls"}}


# ---- PostToolUse ----


class TestPostToolUseHook:
    def test_skips_without_tool_use_id(self):
        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_hook({"tool_name": "Bash"}, None, MagicMock())
        )
        assert result == {}

    def test_skips_unknown_tool_use_id(self):
        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_hook(
                {"tool_name": "Bash", "tool_response": "ok"}, "tu_unknown", MagicMock()
            )
        )
        assert result == {}

    def test_ends_active_run_with_output(self):
        tool_run = MagicMock()
        _active_tool_runs["tu_789"] = (tool_run, 1000.0)

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_hook(
                {"tool_name": "Bash", "tool_response": {"output": "hello"}},
                "tu_789",
                MagicMock(),
            )
        )

        assert result == {}
        assert "tu_789" not in _active_tool_runs
        tool_run.end.assert_called_once_with(
            outputs={"output": "hello"}, error=None
        )
        tool_run.patch.assert_called_once()

    def test_marks_error_from_is_error_flag(self):
        tool_run = MagicMock()
        _active_tool_runs["tu_err"] = (tool_run, 1000.0)

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_response": {"is_error": True, "output": "command failed"},
                },
                "tu_err",
                MagicMock(),
            )
        )

        assert result == {}
        tool_run.end.assert_called_once_with(
            outputs={"is_error": True, "output": "command failed"},
            error="command failed",
        )

    def test_handles_client_managed_run(self):
        run_tree = MagicMock()
        _client_managed_runs["tu_cm"] = run_tree

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_hook(
                {"tool_name": "Task", "tool_response": {"output": "done"}},
                "tu_cm",
                MagicMock(),
            )
        )

        assert result == {}
        assert "tu_cm" not in _client_managed_runs
        run_tree.end.assert_called_once()
        run_tree.patch.assert_called_once()


# ---- PostToolUseFailure ----


class TestPostToolUseFailureHook:
    def test_skips_without_tool_use_id(self):
        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Bash", "error": "boom"}, None, MagicMock()
            )
        )
        assert result == {}

    def test_skips_unknown_tool_use_id(self):
        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Bash", "error": "boom"}, "tu_unknown", MagicMock()
            )
        )
        assert result == {}

    def test_ends_active_run_with_error(self):
        tool_run = MagicMock()
        _active_tool_runs["tu_fail"] = (tool_run, 1000.0)

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Write", "error": "Permission denied"},
                "tu_fail",
                MagicMock(),
            )
        )

        assert result == {}
        assert "tu_fail" not in _active_tool_runs
        tool_run.end.assert_called_once_with(
            outputs={"error": "Permission denied"},
            error="Permission denied",
        )
        tool_run.patch.assert_called_once()

    def test_handles_client_managed_run_failure(self):
        run_tree = MagicMock()
        _client_managed_runs["tu_cm_fail"] = run_tree

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Task", "error": "subagent crashed"},
                "tu_cm_fail",
                MagicMock(),
            )
        )

        assert result == {}
        assert "tu_cm_fail" not in _client_managed_runs
        run_tree.end.assert_called_once_with(
            outputs={"error": "subagent crashed"},
            error="subagent crashed",
        )
        run_tree.patch.assert_called_once()

    def test_uses_default_error_when_missing(self):
        tool_run = MagicMock()
        _active_tool_runs["tu_no_err"] = (tool_run, 1000.0)

        result = asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Bash"},
                "tu_no_err",
                MagicMock(),
            )
        )

        assert result == {}
        tool_run.end.assert_called_once_with(
            outputs={"error": "Unknown error"},
            error="Unknown error",
        )

    def test_removes_from_active_runs(self):
        """Ensure the tool_use_id is removed from _active_tool_runs after failure."""
        tool_run = MagicMock()
        _active_tool_runs["tu_remove"] = (tool_run, 1000.0)

        asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {"tool_name": "Read", "error": "file not found"},
                "tu_remove",
                MagicMock(),
            )
        )

        assert "tu_remove" not in _active_tool_runs


# ---- Hook injection ----


class TestInjectTracingHooks:
    def test_injects_all_three_hooks(self):
        """Verify that _inject_tracing_hooks registers PreToolUse, PostToolUse,
        and PostToolUseFailure matchers."""
        from langsmith.integrations.claude_agent_sdk._client import (
            _inject_tracing_hooks,
        )

        options = MagicMock()
        options.hooks = None

        # Mock HookMatcher so we can track what was created
        with patch(
            "langsmith.integrations.claude_agent_sdk._client.HookMatcher",
            create=True,
        ) as MockMatcher:
            # Make the import inside _inject_tracing_hooks succeed
            import sys

            mock_module = MagicMock()
            mock_module.HookMatcher = MockMatcher
            sys.modules["claude_agent_sdk"] = mock_module
            try:
                _inject_tracing_hooks(options)
            finally:
                del sys.modules["claude_agent_sdk"]

        assert "PreToolUse" in options.hooks
        assert "PostToolUse" in options.hooks
        assert "PostToolUseFailure" in options.hooks

        # Each hook type should have exactly one matcher
        assert len(options.hooks["PreToolUse"]) == 1
        assert len(options.hooks["PostToolUse"]) == 1
        assert len(options.hooks["PostToolUseFailure"]) == 1


# ---- clear_active_tool_runs ----


class TestClearActiveToolRuns:
    def test_cleans_up_orphaned_runs(self):
        tool_run = MagicMock()
        _active_tool_runs["tu_orphan"] = (tool_run, 1000.0)

        client_run = MagicMock()
        _client_managed_runs["tu_cm_orphan"] = client_run

        clear_active_tool_runs()

        assert len(_active_tool_runs) == 0
        assert len(_client_managed_runs) == 0
        tool_run.end.assert_called_once()
        tool_run.patch.assert_called_once()
        client_run.end.assert_called_once()
        client_run.patch.assert_called_once()
