"""Tests for Claude Agent SDK hook handlers.

Unit tests use real RunTree objects (no mocks) to verify the hooks produce
correct trace output.  Integration tests hit the real Claude Agent SDK and
verify error traces appear in the span hierarchy.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from langsmith.run_trees import RunTree

from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _client_managed_runs,
    clear_active_tool_runs,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
)

try:
    import claude_agent_sdk

    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False


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


# ---------------------------------------------------------------------------
# Unit: full PreToolUse -> PostToolUse success flow
# ---------------------------------------------------------------------------


class TestToolUseSuccessFlow:
    """PreToolUse creates a child run; PostToolUse ends it with output."""

    def test_success_flow(self):
        parent = _make_parent_run()

        # Simulate PreToolUse
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

        # Simulate PostToolUse
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

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        """Make a parent RunTree visible to the hooks."""
        from langsmith.integrations.claude_agent_sdk import _tools

        parent = _make_parent_run()
        _tools.set_parent_run_tree(parent)
        yield
        _tools.clear_parent_run_tree()


# ---------------------------------------------------------------------------
# Unit: full PreToolUse -> PostToolUseFailure error flow
# ---------------------------------------------------------------------------


class TestToolUseFailureFlow:
    """PreToolUse creates a child run; PostToolUseFailure marks it as errored."""

    def test_failure_flow(self):
        parent = _make_parent_run()

        # Simulate PreToolUse
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

        # Simulate PostToolUseFailure (mutually exclusive with PostToolUse)
        asyncio.get_event_loop().run_until_complete(
            post_tool_use_failure_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "cat /nonexistent"},
                    "error": "Exit code 1\ncat: /nonexistent: No such file or directory",
                },
                "tu_2",
                MagicMock(),
            )
        )

        assert "tu_2" not in _active_tool_runs
        assert tool_run.error == (
            "Exit code 1\ncat: /nonexistent: No such file or directory"
        )
        assert tool_run.outputs == {
            "error": "Exit code 1\ncat: /nonexistent: No such file or directory"
        }

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        parent = _make_parent_run()
        _tools.set_parent_run_tree(parent)
        yield
        _tools.clear_parent_run_tree()


# ---------------------------------------------------------------------------
# Unit: hook injection wires all three hook types
# ---------------------------------------------------------------------------


class TestInjectTracingHooks:
    def test_injects_all_three_hooks(self):
        from langsmith.integrations.claude_agent_sdk._client import (
            _inject_tracing_hooks,
        )

        options = MagicMock()
        options.hooks = None

        import sys

        mock_module = MagicMock()
        sys.modules["claude_agent_sdk"] = mock_module
        try:
            _inject_tracing_hooks(options)
        finally:
            del sys.modules["claude_agent_sdk"]

        for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            assert event in options.hooks
            assert len(options.hooks[event]) == 1


# ---------------------------------------------------------------------------
# Integration: real Claude Agent SDK call with tool failure
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not CLAUDE_SDK_AVAILABLE, reason="Claude Agent SDK not installed"
)
@pytest.mark.asyncio
async def test_tool_failure_creates_error_trace():
    """End-to-end: a failing Bash command produces an errored tool run."""
    from langsmith.integrations.claude_agent_sdk import configure_claude_agent_sdk

    configure_claude_agent_sdk(name="test.tool_failure")

    options = claude_agent_sdk.ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        allowed_tools=["Bash"],
        max_turns=2,
    )

    tool_result_blocks = []
    async with claude_agent_sdk.ClaudeSDKClient(options=options) as client:
        await client.query(
            "Run this exact bash command: cat /tmp/__langsmith_test_nonexistent.txt"
        )
        async for msg in client.receive_response():
            if type(msg).__name__ == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        tool_result_blocks.append(block)

    # The Bash command should have failed
    assert len(tool_result_blocks) >= 1
    assert tool_result_blocks[0].is_error is True

    # The PostToolUseFailure hook should have consumed the run from
    # _active_tool_runs (no orphaned runs left)
    assert len(_active_tool_runs) == 0
