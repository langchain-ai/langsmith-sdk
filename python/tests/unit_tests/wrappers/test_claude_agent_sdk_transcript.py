"""Tests for transcript parsing."""

from langsmith.integrations.claude_agent_sdk._transcript import (
    group_into_turns,
    read_transcript,
)


class TestReadTranscript:
    """Tests for read_transcript function."""

    def test_reads_jsonl_file(self, tmp_path):
        """Test reading a JSONL file."""
        transcript = tmp_path / "test.jsonl"
        transcript.write_text(
            '{"type": "user", "message": {"role": "user",'
            ' "content": "Hello"}}\n'
            '{"type": "assistant", "message": {"role":'
            ' "assistant", "content": [{"type": "text",'
            ' "text": "Hi"}]}}\n'
        )

        messages = read_transcript(str(transcript))
        assert len(messages) == 2
        assert messages[0]["type"] == "user"
        assert messages[1]["type"] == "assistant"

    def test_handles_missing_file(self):
        """Test handling of missing file."""
        messages = read_transcript("/nonexistent/path.jsonl")
        assert messages == []

    def test_skips_malformed_lines(self, tmp_path):
        """Test skipping malformed JSON lines."""
        transcript = tmp_path / "test.jsonl"
        transcript.write_text(
            '{"type": "user", "message": {"role": "user", "content": "Hello"}}\n'
            "not valid json\n"
            '{"type": "assistant", "message": {"role": "assistant", "content": []}}\n'
        )

        messages = read_transcript(str(transcript))
        assert len(messages) == 2


class TestGroupIntoTurns:
    """Tests for group_into_turns function."""

    def test_groups_simple_turn(self):
        """Test grouping a simple user -> assistant turn."""
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "Hello"},
                "timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "model": "claude-3-5-sonnet",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:05Z",
            },
        ]

        turns = group_into_turns(messages)
        assert len(turns) == 1
        assert turns[0].user_content == "Hello"
        assert len(turns[0].llm_calls) == 1
        assert turns[0].is_complete

    def test_groups_turn_with_tool_use(self):
        """Test grouping a turn with tool use."""
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "What is 2+2?"},
                "timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me calculate that."},
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "calculator",
                            "input": {"expr": "2+2"},
                        },
                    ],
                    "model": "claude-3-5-sonnet",
                    "usage": {"input_tokens": 20, "output_tokens": 10},
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:05Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_123",
                            "content": "4",
                        }
                    ],
                },
                "timestamp": "2024-01-01T00:00:06Z",
            },
        ]

        turns = group_into_turns(messages)
        assert len(turns) == 1
        assert len(turns[0].llm_calls) == 1
        assert len(turns[0].llm_calls[0].tool_calls) == 1
        assert turns[0].llm_calls[0].tool_calls[0].tool_use.name == "calculator"
        assert turns[0].llm_calls[0].tool_calls[0].result["content"] == "4"

    def test_groups_multiple_turns(self):
        """Test grouping multiple turns."""
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "Hello"},
                "timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi!"}],
                    "model": "claude-3-5-sonnet",
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:05Z",
            },
            {
                "type": "user",
                "message": {"role": "user", "content": "How are you?"},
                "timestamp": "2024-01-01T00:00:10Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "I'm doing well!"}],
                    "model": "claude-3-5-sonnet",
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:15Z",
            },
        ]

        turns = group_into_turns(messages)
        assert len(turns) == 2
        assert turns[0].user_content == "Hello"
        assert turns[1].user_content == "How are you?"

    def test_merges_streaming_chunks(self):
        """Test merging multiple assistant chunks with same message ID."""
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "Hello"},
                "timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_123",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi"}],
                    "model": "claude-3-5-sonnet",
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                },
                "timestamp": "2024-01-01T00:00:01Z",
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_123",
                    "role": "assistant",
                    "content": [{"type": "text", "text": " there"}],
                    "model": "claude-3-5-sonnet",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:02Z",
            },
        ]

        turns = group_into_turns(messages)
        assert len(turns) == 1
        assert len(turns[0].llm_calls) == 1
        # Check that text blocks were merged
        text_blocks = [b for b in turns[0].llm_calls[0].content if hasattr(b, "text")]
        assert len(text_blocks) == 1
        assert text_blocks[0].text == "Hi there"

    def test_strips_model_date_suffix(self):
        """Test that model date suffix is stripped."""
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "Hello"},
                "timestamp": "2024-01-01T00:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi"}],
                    "model": "claude-sonnet-4-5-20250929",
                    "stop_reason": "end_turn",
                },
                "timestamp": "2024-01-01T00:00:05Z",
            },
        ]

        turns = group_into_turns(messages)
        assert turns[0].llm_calls[0].model == "claude-sonnet-4-5"
