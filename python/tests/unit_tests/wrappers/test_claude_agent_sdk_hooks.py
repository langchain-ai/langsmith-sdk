"""Unit tests for Claude Agent SDK hooks."""

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from langsmith.integrations.claude_agent_sdk import _hooks as _hooks_module
from langsmith.integrations.claude_agent_sdk._hooks import (
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
    """Reset default hook state between tests."""

    def _reset():
        _hooks_module._default_session.active_tool_runs.clear()
        _hooks_module._default_session.subagent_runs.clear()
        _hooks_module._default_session.pending_agent_tools.clear()
        _hooks_module._default_session.agent_to_tool_mapping.clear()
        _hooks_module._default_session.ended_subagent_runs.clear()
        _hooks_module._default_session.subagent_transcript_paths.clear()
        _hooks_module._default_session.main_transcript_path = None
        _hooks_module._default_session.root_run = None

    _reset()
    yield
    _reset()


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

        assert "tu_1" in _hooks_module._default_session.active_tool_runs
        tool_run, _ = _hooks_module._default_session.active_tool_runs["tu_1"]
        assert tool_run.name == "Bash"
        assert tool_run.run_type == "tool"
        assert tool_run.inputs == {"input": {"command": "echo hi"}}
        assert tool_run.extra["metadata"]["tool_call_id"] == "tu_1"

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

        assert "tu_1" not in _hooks_module._default_session.active_tool_runs
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

        assert "tu_2" in _hooks_module._default_session.active_tool_runs

        asyncio.run(
            post_tool_use_failure_hook(
                {"tool_name": "Bash", "error": ERROR_MSG},
                "tu_2",
                MagicMock(),
            )
        )

        assert "tu_2" not in _hooks_module._default_session.active_tool_runs


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

        assert "tool_1" in _hooks_module._default_session.active_tool_runs
        agent_tool_run, _ = _hooks_module._default_session.active_tool_runs["tool_1"]
        assert agent_tool_run.name == "Agent"

        # The Agent tool_use_id should be pending
        assert "tool_1" in _hooks_module._default_session.pending_agent_tools

        # SubagentStart — note: SDK passes a different tool_use_id
        asyncio.run(
            subagent_start_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_internal_session_id",  # NOT tool_1
                MagicMock(),
            )
        )

        # Subagent run should exist and be nested under Agent tool
        assert "agent_123" in _hooks_module._default_session.subagent_runs
        subagent_run = _hooks_module._default_session.subagent_runs["agent_123"]
        assert subagent_run.name == "foo"
        assert subagent_run.run_type == "chain"
        assert subagent_run.parent_run_id == agent_tool_run.id

        # Inputs should come from the Agent tool's input
        assert subagent_run.inputs == {"agent": "foo"}

        # Mappings should be set
        assert (
            _hooks_module._default_session.agent_to_tool_mapping["agent_123"]
            == "tool_1"
        )
        assert get_subagent_run_by_tool_id("tool_1") == subagent_run

        # Pending should be consumed
        assert "tool_1" not in _hooks_module._default_session.pending_agent_tools

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

        assert "tool_2" in _hooks_module._default_session.active_tool_runs
        tool_run, _ = _hooks_module._default_session.active_tool_runs["tool_2"]
        assert tool_run.name == "Bash"
        assert (
            tool_run.parent_run_id
            == _hooks_module._default_session.subagent_runs["agent_123"].id
        )

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

        run = _hooks_module._default_session.subagent_runs["a1"]
        assert get_subagent_run_by_tool_id("tool_1") is run

        # After SubagentStop, the run is stashed but still findable
        asyncio.run(
            subagent_stop_hook(
                {"agent_id": "a1", "agent_type": "foo"},
                "sdk_1",
                MagicMock(),
            )
        )
        assert "a1" not in _hooks_module._default_session.subagent_runs
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
        subagent_run = _hooks_module._default_session.subagent_runs["agent_123"]

        # Subagent stop — run should be stashed, not ended yet
        asyncio.run(
            subagent_stop_hook(
                {"agent_id": "agent_123", "agent_type": "foo"},
                "sdk_session_id",
                MagicMock(),
            )
        )

        assert "agent_123" not in _hooks_module._default_session.subagent_runs
        assert "tool_1" in _hooks_module._default_session.ended_subagent_runs
        assert (
            _hooks_module._default_session.ended_subagent_runs["tool_1"] is subagent_run
        )
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
        assert "tool_1" not in _hooks_module._default_session.active_tool_runs

        # Subagent outputs should be set but run not yet ended
        assert subagent_run.outputs == {"output": "bar"}
        assert subagent_run.end_time is None

        # Subagent can still be found for LLM nesting
        assert get_subagent_run_by_tool_id("tool_1") is subagent_run

        # clear_active_tool_runs finalises everything
        clear_active_tool_runs()
        assert subagent_run.end_time is not None
        assert len(_hooks_module._default_session.ended_subagent_runs) == 0


class TestTranscriptPathCapture:
    """Pre-tool-use hook captures transcript_path from BaseHookInput."""

    @pytest.fixture(autouse=True)
    def _set_parent(self):
        from langsmith.integrations.claude_agent_sdk import _tools

        _tools.set_parent_run_tree(_make_parent_run())
        yield
        _tools.clear_parent_run_tree()

    def test_captures_transcript_path_from_first_hook(self):
        assert _hooks_module._default_session.main_transcript_path is None

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

        assert (
            _hooks_module._default_session.main_transcript_path
            == "/tmp/sessions/abc.jsonl"
        )

    def test_does_not_overwrite_on_subsequent_hooks(self):
        # Seed the default session's transcript path so the "first writer wins"
        # guard in pre_tool_use_hook kicks in.
        _hooks_module._default_session.main_transcript_path = "/first/path.jsonl"

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

        assert (
            _hooks_module._default_session.main_transcript_path == "/first/path.jsonl"
        )

    def test_clear_active_tool_runs_resets_transcript_path(self):
        _hooks_module._default_session.main_transcript_path = "/some/path.jsonl"
        clear_active_tool_runs()
        assert _hooks_module._default_session.main_transcript_path is None


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
        _hooks_module._default_session.subagent_transcript_paths.append(
            (str(transcript), subagent_run)
        )

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
            "id": "msg_missing",
            "stop_reason": "end_turn",
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

        _hooks_module._default_session.subagent_transcript_paths.append(
            (str(transcript), subagent_run)
        )

        reconcile_from_transcripts(tracker)

        # Should still be the same run, not replaced
        assert tracker.llm_runs_by_message_id["msg_already_seen"] is existing_run


class TestSessionBinding:
    """Small unit guard for hooks bound to a client SessionState."""

    def test_bound_hook_uses_client_session(self):
        import asyncio
        import contextvars

        from langsmith.integrations.claude_agent_sdk._client import (
            _bind_hook_to_session,
        )
        from langsmith.integrations.claude_agent_sdk._hooks import (
            SessionState,
            _set_session_root,
            pre_tool_use_hook,
        )

        parent_run = _make_parent_run()
        session = SessionState()
        _set_session_root(session, parent_run)
        bound_hook = _bind_hook_to_session(pre_tool_use_hook, session)

        contextvars.Context().run(
            lambda: asyncio.run(
                bound_hook(
                    {"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
                    "tool_bound_session",
                    MagicMock(),
                )
            )
        )

        assert "tool_bound_session" in session.active_tool_runs
        assert len(_hooks_module._default_session.active_tool_runs) == 0

    def test_bound_tool_handler_uses_client_session(self):
        from langsmith._internal import _context
        from langsmith.integrations.claude_agent_sdk._client import _wrap_tool_handler
        from langsmith.integrations.claude_agent_sdk._hooks import SessionState

        session = SessionState()
        tool_run = _make_parent_run().create_child(name="get_weather", run_type="tool")
        session.active_tool_runs["tool_1"] = (tool_run, 0.0)
        seen_parent = None

        async def handler(args):
            nonlocal seen_parent
            parent_ref = _context._PARENT_RUN_TREE_REF.get()
            seen_parent = parent_ref() if parent_ref else None
            return {"ok": args["ok"]}

        wrapped = _wrap_tool_handler(handler, session)
        result = asyncio.run(wrapped({"ok": True}))

        assert result == {"ok": True}
        assert seen_parent is tool_run

    def test_unbound_tool_handler_finds_registered_session_by_args(self):
        from langsmith._internal import _context
        from langsmith.integrations.claude_agent_sdk._client import _wrap_tool_handler
        from langsmith.integrations.claude_agent_sdk._hooks import (
            SessionState,
            _register_session,
            _unregister_session,
        )

        session = SessionState()
        tool_run = _make_parent_run().create_child(
            name="mcp__weather__get_weather",
            run_type="tool",
            inputs={"input": {"city": "SF"}},
        )
        session.active_tool_runs["tool_1"] = (tool_run, 0.0)
        token = _register_session(session)
        seen_parent = None

        async def handler(args):
            nonlocal seen_parent
            parent_ref = _context._PARENT_RUN_TREE_REF.get()
            seen_parent = parent_ref() if parent_ref else None
            return {"ok": True}

        try:
            wrapped = _wrap_tool_handler(handler, tool_name="get_weather")
            result = asyncio.run(wrapped({"city": "SF"}))
        finally:
            _unregister_session(session, token)

        assert result == {"ok": True}
        assert seen_parent is tool_run


class _FakeAssistantMessage:
    """Stand-in for ``claude_agent_sdk.AssistantMessage``.

    The run builder dispatches on ``type(msg).__name__``, so the class name
    matters as much as the attributes.
    """

    def __init__(
        self,
        content,
        message_id,
        stop_reason=None,
        model="claude-test",
        parent_tool_use_id=None,
    ):
        self.content = content
        self.message_id = message_id
        self.stop_reason = stop_reason
        self.model = model
        self.parent_tool_use_id = parent_tool_use_id


_FakeAssistantMessage.__name__ = "AssistantMessage"


def _write_transcript(path, entries):
    """Write entries as a Claude CLI JSONL transcript; return the path."""
    import json

    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return str(path)


def _streamed_llm_run(parent, *, message_id, stop_reason):
    """Build an LLM run the way the live stream would, for reconcile tests."""
    from langsmith.integrations.claude_agent_sdk._client import (
        begin_llm_run_from_assistant_messages,
    )

    _, run = begin_llm_run_from_assistant_messages(
        [
            _FakeAssistantMessage(
                content=[{"type": "text", "text": "partial"}],
                message_id=message_id,
                stop_reason=stop_reason,
            )
        ],
        prompt="go",
        history=[],
        parent=parent,
    )
    return run


class TestStopReasonAndResponseId:
    """LSDK-522: `stop_reason` and the Anthropic message id reach run outputs.

    Values are provider-native and stored under the provider's own key names,
    matching `wrappers/_anthropic.py`. Mapping them onto the OTel semantic
    conventions is the exporter's job and is not covered here.
    """

    def test_live_message_with_stop_reason_is_stored(self):
        run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_live", stop_reason="tool_use"
        )

        assert run is not None
        assert run.outputs["stop_reason"] == "tool_use"
        assert run.outputs["id"] == "msg_live"
        assert run.outputs["role"] == "assistant"

    def test_absent_stop_reason_is_omitted_not_nulled(self):
        """The live stream relays ``stop_reason: null``; do not persist that."""
        run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_live", stop_reason=None
        )

        assert run is not None
        assert "stop_reason" not in run.outputs
        assert run.outputs["id"] == "msg_live"

    def test_same_turn_merge_keeps_the_last_stop_reason(self):
        """A turn can arrive as several events; only the final one has it."""
        from langsmith.integrations.claude_agent_sdk import _tools
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle

        _tools.set_parent_run_tree(_make_parent_run())
        try:
            tracker = TurnLifecycle()
            history: list = []
            for text, reason in (("thinking", None), ("done", "end_turn")):
                tracker.start_llm_run(
                    _FakeAssistantMessage(
                        content=[{"type": "text", "text": text}],
                        message_id="msg_split",
                        stop_reason=reason,
                    ),
                    prompt="go",
                    history=history,
                )
        finally:
            _tools.clear_parent_run_tree()

        run = tracker.llm_runs_by_message_id["msg_split"]
        assert run.outputs["stop_reason"] == "end_turn"
        assert run.outputs["id"] == "msg_split"

    def test_transcript_patches_a_streamed_run_that_had_no_stop_reason(self, tmp_path):
        """The production path: the stream has no reason, the transcript does.

        This is what the customer actually hits. A fix that only writes the
        live value would leave this run with no stop reason at all.
        """
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            reconcile_from_transcripts,
        )

        tracker = TurnLifecycle()
        run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_stream", stop_reason=None
        )
        tracker.llm_runs_by_message_id["msg_stream"] = run
        assert "stop_reason" not in run.outputs

        _hooks_module._default_session.main_transcript_path = _write_transcript(
            tmp_path / "main.jsonl",
            [
                {
                    "type": "assistant",
                    "message": {"id": "msg_stream", "stop_reason": None},
                },
                {
                    "type": "assistant",
                    "message": {"id": "msg_stream", "stop_reason": "tool_use"},
                },
            ],
        )

        reconcile_from_transcripts(tracker)

        assert run.outputs["stop_reason"] == "tool_use"
        assert run.outputs["id"] == "msg_stream"

    def test_result_message_fills_the_final_turn(self):
        """The last turn has no other source for its stop reason.

        Its assistant events carry ``stop_reason: null`` and the CLI has not
        yet flushed the matching transcript entry when reconcile runs, so
        without this the closing ``end_turn`` is lost on every conversation.
        """
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle

        tracker = TurnLifecycle()
        tracker.last_main_run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_final", stop_reason=None
        )

        tracker.set_stop_reason_from_result(MagicMock(stop_reason="end_turn"))

        assert tracker.last_main_run.outputs["stop_reason"] == "end_turn"

    def test_result_message_skips_a_trailing_subagent_turn(self):
        """A conversation can end while a subagent spoke last.

        Interrupt, max turns or a denied permission all leave a subagent
        turn as the most recent run. The ``ResultMessage`` stop reason
        describes the conversation, so it belongs to the main agent's final
        turn — not to whichever subagent happened to be talking.
        """
        from langsmith.integrations.claude_agent_sdk import _tools
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle

        _tools.set_parent_run_tree(_make_parent_run())
        try:
            tracker = TurnLifecycle()
            history: list = []
            tracker.start_llm_run(
                _FakeAssistantMessage(
                    content=[{"type": "text", "text": "delegating"}],
                    message_id="msg_main",
                ),
                prompt="go",
                history=history,
            )
            tracker.start_llm_run(
                _FakeAssistantMessage(
                    content=[{"type": "text", "text": "subagent working"}],
                    message_id="msg_sub",
                    parent_tool_use_id="toolu_agent_1",
                ),
                prompt=None,
                history=history,
            )
        finally:
            _tools.clear_parent_run_tree()

        tracker.set_stop_reason_from_result(MagicMock(stop_reason="max_turns"))

        runs = tracker.llm_runs_by_message_id
        assert runs["msg_main"].outputs["stop_reason"] == "max_turns"
        assert "stop_reason" not in runs["msg_sub"].outputs

    def test_result_message_does_not_override_a_known_stop_reason(self):
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle

        tracker = TurnLifecycle()
        tracker.last_main_run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_final", stop_reason="tool_use"
        )

        tracker.set_stop_reason_from_result(MagicMock(stop_reason="end_turn"))

        assert tracker.last_main_run.outputs["stop_reason"] == "tool_use"

    def test_transcript_wins_over_the_result_message_value(self, tmp_path):
        """Per-message transcript data beats the conversation-level value."""
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            reconcile_from_transcripts,
        )

        tracker = TurnLifecycle()
        run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_final", stop_reason=None
        )
        tracker.last_main_run = run
        tracker.llm_runs_by_message_id["msg_final"] = run
        tracker.set_stop_reason_from_result(MagicMock(stop_reason="end_turn"))
        assert run.outputs["stop_reason"] == "end_turn"

        _hooks_module._default_session.main_transcript_path = _write_transcript(
            tmp_path / "main.jsonl",
            [
                {
                    "type": "assistant",
                    "message": {"id": "msg_final", "stop_reason": "max_tokens"},
                },
            ],
        )

        reconcile_from_transcripts(tracker)

        assert run.outputs["stop_reason"] == "max_tokens"

    def test_reconcile_does_not_invent_an_unknown_stop_reason(self, tmp_path):
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            reconcile_from_transcripts,
        )

        tracker = TurnLifecycle()
        run = _streamed_llm_run(
            _make_parent_run(), message_id="msg_stream", stop_reason=None
        )
        tracker.llm_runs_by_message_id["msg_stream"] = run

        _hooks_module._default_session.main_transcript_path = _write_transcript(
            tmp_path / "main.jsonl",
            [
                {
                    "type": "assistant",
                    "message": {"id": "msg_stream", "stop_reason": None},
                },
            ],
        )

        reconcile_from_transcripts(tracker)

        # The id is always knowable; the stop reason is never invented.
        assert run.outputs["id"] == "msg_stream"
        assert "stop_reason" not in run.outputs

    def test_transcript_patches_usage_alongside_stop_reason(self, tmp_path):
        """Usage and stop reason share one reconcile pass and one reader.

        Nothing else covers the usage half, so a regression there would be
        silent.
        """
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            reconcile_from_transcripts,
        )

        tracker = TurnLifecycle()
        run = _streamed_llm_run(_make_parent_run(), message_id="m1", stop_reason=None)
        tracker.llm_runs_by_message_id["m1"] = run

        _hooks_module._default_session.main_transcript_path = _write_transcript(
            tmp_path / "main.jsonl",
            [
                # Partial chunk: low output_tokens, no stop reason yet.
                {
                    "type": "assistant",
                    "message": {
                        "id": "m1",
                        "stop_reason": None,
                        "usage": {"input_tokens": 11, "output_tokens": 1},
                    },
                },
                # Final chunk wins for both fields.
                {
                    "type": "assistant",
                    "message": {
                        "id": "m1",
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 11, "output_tokens": 7},
                    },
                },
            ],
        )

        reconcile_from_transcripts(tracker)

        usage = run.extra["metadata"]["usage_metadata"]
        assert usage["input_tokens"] == 11
        assert usage["output_tokens"] == 7
        assert usage["total_tokens"] == 18
        assert run.outputs["stop_reason"] == "end_turn"

    def test_multi_turn_transcript_patches_each_turn(self, tmp_path):
        """Reuses read_llm_turns_from_transcript, which keys by message id."""
        from langsmith.integrations.claude_agent_sdk._client import TurnLifecycle
        from langsmith.integrations.claude_agent_sdk._transcripts import (
            reconcile_from_transcripts,
        )

        tracker = TurnLifecycle()
        parent = _make_parent_run()
        for mid in ("m1", "m2"):
            tracker.llm_runs_by_message_id[mid] = _streamed_llm_run(
                parent, message_id=mid, stop_reason=None
            )

        _hooks_module._default_session.main_transcript_path = _write_transcript(
            tmp_path / "main.jsonl",
            [
                {"type": "user", "message": {"content": "hi"}},
                {"type": "assistant", "message": {"id": "m1", "stop_reason": None}},
                {
                    "type": "assistant",
                    "message": {"id": "m1", "stop_reason": "tool_use"},
                },
                {
                    "type": "assistant",
                    "message": {"id": "m2", "stop_reason": "end_turn"},
                },
            ],
        )

        reconcile_from_transcripts(tracker)

        assert tracker.llm_runs_by_message_id["m1"].outputs["stop_reason"] == "tool_use"
        assert tracker.llm_runs_by_message_id["m2"].outputs["stop_reason"] == "end_turn"
