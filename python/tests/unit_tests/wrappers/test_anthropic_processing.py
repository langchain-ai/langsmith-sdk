"""Unit tests for Anthropic wrapper processing functions."""

import warnings
from unittest.mock import MagicMock

import pytest

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


def _collect_pydantic_warnings(caught):
    return [
        w
        for w in caught
        if "PydanticSerializationUnexpectedValue" in str(w.message)
        or "Pydantic serializer warnings" in str(w.message)
    ]


class TestParsedMessageSerialization:
    """Anthropic's ParsedMessage / ParsedBetaMessage trigger Pydantic
    serializer warnings when dumped because ``parsed_output`` and the
    parsed content-block union do not match the base class's field types.

    The wrapper handles them via a dedicated path that dumps each content
    block with its ``__api_exclude__`` and re-attaches ``parsed_output``,
    avoiding the warnings entirely while preserving the parsed values.
    """

    def test_parsed_beta_message_from_real_anthropic_parser(self):
        """End-to-end check using Anthropic's own ``parse_beta_response``.

        This produces the exact ``ParsedBetaMessage[TypeVar]`` shape the SDK
        returns from ``client.beta.messages.parse(...)`` and is what the LSDK-166
        bug report originally reproduced.
        """
        pydantic_mod = pytest.importorskip("pydantic")
        parse_module = pytest.importorskip("anthropic.lib._parse._response")
        beta_message_module = pytest.importorskip("anthropic.types.beta.beta_message")
        beta_text_block_module = pytest.importorskip(
            "anthropic.types.beta.beta_text_block"
        )

        class WeatherResponse(pydantic_mod.BaseModel):
            city: str
            temp: str

        text_block = beta_text_block_module.BetaTextBlock(
            type="text",
            text='{"city": "SF", "temp": "62F"}',
            citations=None,
        )
        beta_msg = beta_message_module.BetaMessage(
            id="msg_1",
            role="assistant",
            content=[text_block],
            model="claude-opus-4-6",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        parsed_msg = parse_module.parse_beta_response(
            output_format=WeatherResponse, response=beta_msg
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            outputs = _message_to_outputs(parsed_msg)

        assert not _collect_pydantic_warnings(caught), [
            str(w.message) for w in _collect_pydantic_warnings(caught)
        ]
        assert outputs["content"][0]["type"] == "text"
        assert outputs["content"][0]["parsed_output"] == {
            "city": "SF",
            "temp": "62F",
        }
        assert outputs["parsed_output"] == {"city": "SF", "temp": "62F"}
        assert outputs["usage_metadata"]["input_tokens"] == 10
        assert outputs["usage_metadata"]["output_tokens"] == 5

    def test_parsed_message_constructed_directly(self):
        anthropic_types = pytest.importorskip("anthropic.types")
        pydantic_mod = pytest.importorskip("pydantic")

        ParsedMessage = anthropic_types.ParsedMessage
        ParsedTextBlock = anthropic_types.ParsedTextBlock

        class WeatherResponse(pydantic_mod.BaseModel):
            city: str
            temp: str

        parsed = WeatherResponse(city="SF", temp="62F")
        block = ParsedTextBlock.model_construct(
            type="text",
            text='{"city": "SF", "temp": "62F"}',
            parsed_output=parsed,
            citations=None,
        )
        msg = ParsedMessage.model_construct(
            id="msg_1",
            role="assistant",
            content=[block],
            model="claude-opus-4-6",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage={"input_tokens": 10, "output_tokens": 5},
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            outputs = _message_to_outputs(msg)

        assert not _collect_pydantic_warnings(caught)
        assert outputs["content"][0]["parsed_output"] == {
            "city": "SF",
            "temp": "62F",
        }
        assert outputs["content"][0]["type"] == "text"

    def test_non_parsed_message_uses_default_dump(self):
        """Regular Anthropic Messages should still go through ``model_dump``."""

        msg = MagicMock()
        msg.model_dump.return_value = {
            "id": "msg_1",
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "model": "claude-x",
            "stop_reason": "end_turn",
            "type": "message",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }
        type(msg).__name__ = "Message"

        outputs = _message_to_outputs(msg)
        assert outputs["content"] == [{"type": "text", "text": "hi"}]
        assert outputs["usage_metadata"]["input_tokens"] == 1
        msg.model_dump.assert_called_once()

    def test_model_dump_without_warnings_kwarg_falls_back(self):
        """Older pydantic models without ``warnings`` kwarg still work."""

        class LegacyMessage:
            def model_dump(self, **kwargs):
                if "warnings" in kwargs:
                    raise TypeError("unexpected kwarg 'warnings'")
                return {
                    "id": "msg_legacy",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi"}],
                    "model": "claude-x",
                    "stop_reason": "end_turn",
                    "type": "message",
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                }

        outputs = _message_to_outputs(LegacyMessage())
        assert outputs["content"] == [{"type": "text", "text": "hi"}]
        assert outputs["usage_metadata"]["input_tokens"] == 1
