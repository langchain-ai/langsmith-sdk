"""Unit tests for Claude Agent SDK hooks."""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from langsmith.integrations.claude_agent_sdk import _hooks as _hooks_module
from langsmith.integrations.claude_agent_sdk._hooks import (
    _active_tool_runs,
    _agent_to_tool_mapping,
    _ended_subagent_runs,
    _pending_agent_tools,
    _subagent_runs,
    _subagent_transcript_paths,
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
    _subagent_transcript_paths.clear()
    _hooks_module._main_transcript_path = None
    yield
    _active_tool_runs.clear()
    _subagent_runs.clear()
    _pending_agent_tools.clear()
    _agent_to_tool_mapping.clear()
    _ended_subagent_runs.clear()
    _subagent_transcript_paths.clear()
    _hooks_module._main_transcript_path = None


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
        assert tool_run.extra["metadata"]["ls_tool_call_id"] == "tu_1"

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

        assert "tu_2" in _active_tool_runs

        asyncio.run(
            post_tool_use_failure_hook(
                {"tool_name": "Bash", "error": ERROR_MSG},
                "tu_2",
                MagicMock(),
            )
        )

        assert "tu_2" not in _active_tool_runs


class TestInjectTracingHooks:
    def test_injects_all_hooks(self):
        from langsmith.integrations.claude_agent_sdk._client import (
            _inject_tracing_hooks,
        )

        options = MagicMock()
        options.hooks = None

        original_module = sys.modules.get("claude_agent_sdk")
        mock_module = MagicMock()
        sys.modules["claude_agent_sdk"] = mock_module
        try:
            _inject_tracing_hooks(options)
        finally:
            if original_module is not None:
                sys.modules["claude_agent_sdk"] = original_module
            else:
                sys.modules.pop("claude_agent_sdk", None)

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

    def test_tool_inside_subagent_nests_under_subagent(self):
        """Tools inside a subagent should nest under the subagent run."""
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


class TestTranscriptPathCapture:
    """Pre-tool-use hook captures transcript_path from BaseHookInput."""

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        _tools.set_parent_run_tree(_make_parent_run())
        yield
        _tools.clear_parent_run_tree()

    def test_captures_transcript_path_from_first_hook(self):
        assert _hooks_module._main_transcript_path is None

        asyncio.run(
            pre_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "echo hi"},
                    "transcript_path": "/tmp/sessions/abc.jsonl",
                },
                "tu_1",
                MagicMock(),
            )
        )

        assert _hooks_module._main_transcript_path == "/tmp/sessions/abc.jsonl"

    def test_does_not_overwrite_on_subsequent_hooks(self):
        _hooks_module._main_transcript_path = "/first/path.jsonl"

        asyncio.run(
            pre_tool_use_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {},
                    "transcript_path": "/second/path.jsonl",
                },
                "tu_2",
                MagicMock(),
            )
        )

        assert _hooks_module._main_transcript_path == "/first/path.jsonl"

    def test_clear_active_tool_runs_resets_transcript_path(self):
        _hooks_module._main_transcript_path = "/some/path.jsonl"
        clear_active_tool_runs()
        assert _hooks_module._main_transcript_path is None


class TestReadLLMTurnsFromTranscript:
    """Unit tests for read_llm_turns_from_transcript."""

    def test_extracts_final_entries_only(self, tmp_path):
        from langsmith.integrations.claude_agent_sdk._usage import (
            read_llm_turns_from_transcript,
        )

        transcript = tmp_path / "session.jsonl"
        import json

        lines = [
            # Initial user prompt
            {
                "type": "user",
                "message": {"content": "echo hello"},
            },
            # Partial (streaming) — stop_reason null
            {
                "type": "assistant",
                "message": {
                    "id": "msg_001",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": "Thinking..."}],
                    "stop_reason": None,
                    "usage": {"input_tokens": 100, "output_tokens": 3},
                },
                "timestamp": "2025-01-01T00:00:00.000Z",
            },
            # Final — stop_reason set
            {
                "type": "assistant",
                "message": {
                    "id": "msg_001",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tu_1",
                            "name": "Bash",
                            "input": {"command": "echo hello"},
                        },
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 100, "output_tokens": 42},
                },
                "timestamp": "2025-01-01T00:00:01.000Z",
            },
            # User message (tool result)
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tu_1",
                            "content": "hello",
                        },
                    ]
                },
            },
            # Second turn — partial
            {
                "type": "assistant",
                "message": {
                    "id": "msg_002",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": "d"}],
                    "stop_reason": None,
                    "usage": {"input_tokens": 150, "output_tokens": 1},
                },
                "timestamp": "2025-01-01T00:00:02.000Z",
            },
            # Second turn — final
            {
                "type": "assistant",
                "message": {
                    "id": "msg_002",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": "done"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 150, "output_tokens": 5},
                },
                "timestamp": "2025-01-01T00:00:03.000Z",
            },
        ]
        transcript.write_text("\n".join(json.dumps(entry) for entry in lines))

        turns = read_llm_turns_from_transcript(str(transcript))

        assert len(turns) == 2

        assert turns[0]["message_id"] == "msg_001"
        assert turns[0]["stop_reason"] == "tool_use"
        assert turns[0]["usage"]["output_tokens"] == 42
        # First turn should see only the initial user prompt
        assert turns[0]["input_messages"] == [
            {"role": "user", "content": "echo hello"},
        ]

        assert turns[1]["message_id"] == "msg_002"
        assert turns[1]["stop_reason"] == "end_turn"
        assert turns[1]["content"] == [{"type": "text", "text": "done"}]
        # Second turn should see full conversation history
        assert turns[1]["input_messages"] == [
            {"role": "user", "content": "echo hello"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "Bash",
                        "input": {"command": "echo hello"},
                    },
                ],
            },
            {"role": "tool", "content": "hello", "tool_call_id": "tu_1"},
        ]

    def test_empty_file(self, tmp_path):
        from langsmith.integrations.claude_agent_sdk._usage import (
            read_llm_turns_from_transcript,
        )

        transcript = tmp_path / "empty.jsonl"
        transcript.write_text("")
        assert read_llm_turns_from_transcript(str(transcript)) == []

    def test_missing_file(self):
        from langsmith.integrations.claude_agent_sdk._usage import (
            read_llm_turns_from_transcript,
        )

        assert read_llm_turns_from_transcript("/nonexistent/path.jsonl") == []


class TestMissingSubagentLLMRuns:
    """reconcile_from_transcripts creates LLM runs for subagent turns
    that were not seen in the live stream."""

    def test_creates_missing_llm_run_from_transcript(self, tmp_path):
        import json

        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            LLM_RUN_NAME,
            reconcile_from_transcripts,
        )

        # Create a subagent run
        parent = _make_parent_run()
        subagent_run = parent.create_child(
            name="foo",
            run_type="chain",
        )

        # Write a transcript with 2 turns
        transcript = tmp_path / "subagent.jsonl"
        lines = [
            {
                "type": "assistant",
                "message": {
                    "id": "msg_seen",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [
                        {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                },
                "timestamp": "2025-01-01T00:00:01.000Z",
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_missing",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": "done"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 150, "output_tokens": 5},
                },
                "timestamp": "2025-01-01T00:00:03.000Z",
            },
        ]
        transcript.write_text("\n".join(json.dumps(entry) for entry in lines))

        # Set up tracker with msg_seen already created
        tracker = TurnLifecycle()
        existing_run = parent.create_child(
            name=LLM_RUN_NAME,
            run_type="llm",
        )
        tracker.llm_runs_by_message_id["msg_seen"] = existing_run

        # Register subagent transcript
        _subagent_transcript_paths.append((str(transcript), subagent_run))

        reconcile_from_transcripts(tracker)

        # msg_missing should now have an LLM run
        assert "msg_missing" in tracker.llm_runs_by_message_id
        new_run = tracker.llm_runs_by_message_id["msg_missing"]
        assert new_run.name == LLM_RUN_NAME
        assert new_run.run_type == "llm"
        assert new_run.parent_run_id == subagent_run.id
        assert new_run.outputs == {
            "content": [{"type": "text", "text": "done"}],
            "role": "assistant",
        }

    def test_skips_already_seen_message_ids(self, tmp_path):
        import json

        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            LLM_RUN_NAME,
            reconcile_from_transcripts,
        )

        parent = _make_parent_run()
        subagent_run = parent.create_child(
            name="foo",
            run_type="chain",
        )

        transcript = tmp_path / "subagent.jsonl"
        lines = [
            {
                "type": "assistant",
                "message": {
                    "id": "msg_already_seen",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": "hi"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 50, "output_tokens": 2},
                },
            },
        ]
        transcript.write_text("\n".join(json.dumps(entry) for entry in lines))

        tracker = TurnLifecycle()
        existing_run = parent.create_child(
            name=LLM_RUN_NAME,
            run_type="llm",
        )
        tracker.llm_runs_by_message_id["msg_already_seen"] = existing_run

        _subagent_transcript_paths.append((str(transcript), subagent_run))

        reconcile_from_transcripts(tracker)

        # Should still be the same run, not replaced
        assert tracker.llm_runs_by_message_id["msg_already_seen"] is existing_run
