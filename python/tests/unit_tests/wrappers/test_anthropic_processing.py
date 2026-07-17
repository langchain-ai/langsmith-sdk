"""Unit tests for Anthropic wrapper processing functions."""

import asyncio
import functools
import inspect
import warnings
from unittest.mock import MagicMock, patch

from langsmith._internal._orjson import loads as _loads
from langsmith.wrappers._anthropic import (
    _create_usage_metadata,
    _get_wrapper,
    _is_async_or_wraps_async,
    _message_to_outputs,
)


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


class TestMessageToOutputsParsedMessage:
    """Test that _message_to_outputs suppresses Pydantic warnings for parsed
    messages."""

    def test_no_pydantic_warning_for_parsed_beta_message(self):
        """ParsedBetaMessage triggers PydanticSerializationUnexpectedValue when
        model_dump() is called directly. Verify no warnings leak out."""
        msg = MagicMock()
        # Simulate ParsedBetaMessage: has parsed_output and emits warning on model_dump
        msg.parsed_output = MagicMock()

        def _model_dump_with_warning():
            warnings.warn(
                "PydanticSerializationUnexpectedValue",
                UserWarning,
                stacklevel=2,
            )
            return {
                "id": "msg_beta_123",
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello"}],
                "model": "claude-sonnet-4-20250514",
                "stop_reason": "end_turn",
                "type": "message",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

        msg.model_dump.side_effect = _model_dump_with_warning

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _message_to_outputs(msg)

        assert len(caught) == 0, (
            f"Expected no warnings, got: {[str(w.message) for w in caught]}"
        )
        assert result["content"] == [{"type": "text", "text": "Hello"}]

    def test_regular_message_warnings_not_suppressed(self):
        """For regular (non-parsed) messages, warnings from model_dump are not
        suppressed."""
        msg = MagicMock()
        del msg.parsed_output  # ensure attribute does not exist

        def _model_dump_with_warning():
            warnings.warn("some other warning", UserWarning, stacklevel=2)
            return {
                "id": "msg_123",
                "role": "assistant",
                "content": "Hello",
                "model": "claude-sonnet-4-20250514",
                "stop_reason": "end_turn",
                "type": "message",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

        msg.model_dump.side_effect = _model_dump_with_warning

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _message_to_outputs(msg)

        assert len(caught) == 1
        assert "some other warning" in str(caught[0].message)


class TestOtelInterop:
    """Tests for correct behaviour when OpenTelemetry instruments before LangSmith.

    OpenTelemetry's ``AnthropicInstrumentor`` uses *wrapt* to patch
    ``AsyncMessages.create`` at the *class* level with a sync wrapper that
    internally calls the original coroutine function and returns the resulting
    coroutine object.  LangSmith then patches at the *instance* level.  The
    sync wrapper hides the async nature from a naive ``iscoroutinefunction``
    check, which causes LangSmith to select the sync code path and record the
    raw coroutine object as the trace output.

    The fix: ``_is_async_or_wraps_async`` walks the ``__wrapped__`` chain, and
    ``acreate`` creates an async proxy when the detected callable is sync but
    its wrapped original is async.
    """

    def test_is_async_or_wraps_async_direct_async(self):
        async def afunc():
            return 42

        assert _is_async_or_wraps_async(afunc) is True

    def test_is_async_or_wraps_async_plain_sync(self):
        def func():
            return 42

        assert _is_async_or_wraps_async(func) is False

    def test_is_async_or_wraps_async_sync_wrapping_async(self):
        """Sync wrapper whose __wrapped__ points to an async function is detected."""
        async def original_async():
            return 42

        @functools.wraps(original_async)
        def sync_wrapper(*args, **kwargs):
            return original_async(*args, **kwargs)

        assert _is_async_or_wraps_async(sync_wrapper) is True

    def test_is_async_or_wraps_async_multi_level_chain(self):
        """Async function nested two __wrapped__ levels deep is still detected."""
        async def original_async():
            return 42

        @functools.wraps(original_async)
        def inner_wrapper(*args, **kwargs):
            return original_async(*args, **kwargs)

        @functools.wraps(inner_wrapper)
        def outer_wrapper(*args, **kwargs):
            return inner_wrapper(*args, **kwargs)

        assert _is_async_or_wraps_async(outer_wrapper) is True

    def test_get_wrapper_returns_async_for_otel_style_sync_wrapper(self):
        """_get_wrapper must select acreate when the original has __wrapped__ async."""
        async def real_create(**kwargs):
            return {"id": "msg_123"}

        @functools.wraps(real_create)
        def otel_sync_wrapper(**kwargs):
            # OTel pattern: sync closure that returns a coroutine object
            return real_create(**kwargs)

        wrapper = _get_wrapper(
            otel_sync_wrapper,
            name="test",
            reduce_fn=lambda x: x,
            prepopulated_invocation_params={},
            tracing_extra={},
        )

        assert inspect.iscoroutinefunction(wrapper), (
            "_get_wrapper should return an async wrapper when the original function "
            "wraps an async method (OTel instrumentation pattern)"
        )

    def test_acreate_returns_real_result_not_coroutine(self):
        """acreate must return the awaited result, not a coroutine object."""
        expected = {"id": "msg_123", "content": "hi"}

        async def real_create(**kwargs):
            return expected

        @functools.wraps(real_create)
        def otel_sync_wrapper(**kwargs):
            return real_create(**kwargs)

        with patch("langsmith.utils.tracing_is_enabled", return_value=False):
            wrapper = _get_wrapper(
                otel_sync_wrapper,
                name="test",
                reduce_fn=lambda x: x,
                prepopulated_invocation_params={},
                tracing_extra={},
            )
            result = asyncio.run(wrapper(model="claude-3-5-haiku", max_tokens=10, messages=[]))

        assert not inspect.iscoroutine(result), (
            "Result must be the awaited message dict, not a coroutine object"
        )
        assert result == expected
