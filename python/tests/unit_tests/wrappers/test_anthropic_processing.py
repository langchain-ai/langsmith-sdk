"""Unit tests for Anthropic wrapper processing functions."""

from unittest.mock import MagicMock

from langsmith._internal._orjson import loads as _loads
from langsmith.wrappers._anthropic import _create_usage_metadata, _message_to_outputs


class TestCreateUsageMetadata:
    """Test _create_usage_metadata function."""

    def test_no_cache(self):
        result = _create_usage_metadata({"input_tokens": 100, "output_tokens": 50})
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert "input_token_details" not in result

    def test_legacy_cache_tokens(self):
        # Anthropic reports cache tokens additively (not as subsets of input_tokens).
        # input_tokens=19 is the NON-cached portion; cache tokens are on top.
        result = _create_usage_metadata(
            {
                "input_tokens": 19,
                "output_tokens": 100,
                "cache_read_input_tokens": 32000,
                "cache_creation_input_tokens": 7000,
            }
        )
        assert result["input_tokens"] == 39019  # 19 + 32000 + 7000
        assert result["output_tokens"] == 100
        assert result["total_tokens"] == 39119  # 39019 + 100
        assert result["input_token_details"]["cache_read"] == 32000
        assert result["input_token_details"]["cache_creation"] == 7000

    def test_new_format_cache_object(self):
        result = _create_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 500,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 800,
                    "ephemeral_1h_input_tokens": 200,
                },
            }
        )
        assert result["input_tokens"] == 1600  # 100 + 500 + 800 + 200
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 1650  # 1600 + 50
        assert result["input_token_details"]["cache_read"] == 500
        assert result["input_token_details"]["ephemeral_5m_input_tokens"] == 800
        assert result["input_token_details"]["ephemeral_1h_input_tokens"] == 200

    def test_only_cache_read(self):
        result = _create_usage_metadata(
            {
                "input_tokens": 50,
                "output_tokens": 30,
                "cache_read_input_tokens": 1000,
            }
        )
        assert result["input_tokens"] == 1050  # 50 + 1000
        assert result["output_tokens"] == 30
        assert result["total_tokens"] == 1080  # 1050 + 30
        assert result["input_token_details"]["cache_read"] == 1000

    def test_zero_cache_tokens_not_in_details(self):
        # Zero-valued cache fields should not appear in input_token_details
        result = _create_usage_metadata(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        )
        assert result["input_tokens"] == 100
        assert result["total_tokens"] == 150
        assert "input_token_details" not in result

    def test_empty_usage(self):
        result = _create_usage_metadata({})
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0
        assert result["total_tokens"] == 0


class TestMessageToOutputsToolCalls:
    """Test that _message_to_outputs converts Anthropic tool_use blocks
    to the OpenAI-compatible tool_calls format the LangSmith UI expects."""

    @staticmethod
    def _make_message(content, usage=None, stop_reason="end_turn"):
        msg = MagicMock()
        msg.model_dump.return_value = {
            "id": "msg_123",
            "role": "assistant",
            "content": content,
            "model": "claude-sonnet-4-20250514",
            "stop_reason": stop_reason,
            "type": "message",
            "usage": usage or {"input_tokens": 10, "output_tokens": 5},
        }
        return msg

    def test_tool_use_converted_to_tool_calls(self):
        msg = self._make_message(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "get_weather",
                    "input": {"location": "SF", "unit": "celsius"},
                },
            ],
            stop_reason="tool_use",
        )
        result = _message_to_outputs(msg)

        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "toolu_abc"
        assert tc["type"] == "function"
        assert tc["index"] == 0
        assert tc["function"]["name"] == "get_weather"
        assert _loads(tc["function"]["arguments"]) == {
            "location": "SF",
            "unit": "celsius",
        }

    def test_text_only_has_no_tool_calls(self):
        msg = self._make_message([{"type": "text", "text": "Hello!"}])
        result = _message_to_outputs(msg)

        assert "tool_calls" not in result
        assert result["content"] == [{"type": "text", "text": "Hello!"}]

    def test_text_stripped_from_content_when_tool_calls_present(self):
        msg = self._make_message(
            [
                {"type": "text", "text": "Let me check."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "search",
                    "input": {"q": "weather"},
                },
            ],
            stop_reason="tool_use",
        )
        result = _message_to_outputs(msg)

        assert result["content"] == "Let me check."
        assert len(result["tool_calls"]) == 1

    def test_multiple_tool_calls_indexed(self):
        msg = self._make_message(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "get_weather",
                    "input": {"location": "SF"},
                },
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "get_stock",
                    "input": {"ticker": "AAPL"},
                },
            ],
            stop_reason="tool_use",
        )
        result = _message_to_outputs(msg)

        assert len(result["tool_calls"]) == 2
        assert result["tool_calls"][0]["index"] == 0
        assert result["tool_calls"][1]["index"] == 1
        assert result["tool_calls"][0]["function"]["name"] == "get_weather"
        assert result["tool_calls"][1]["function"]["name"] == "get_stock"
