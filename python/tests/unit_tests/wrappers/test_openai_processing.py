"""Unit tests for OpenAI wrapper processing functions."""

import asyncio
import functools

import pytest

from langsmith.wrappers._openai import (
    _get_wrapper,
    _infer_invocation_params,
    _is_async_or_wraps_async,
    _reduce_chat,
)


def test_infer_invocation_params_copies_request_metadata():
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {
            "model": "gpt-4o-mini",
            "metadata": {
                "customer_id": "customer-123",
                "environment": "test",
            },
        },
    )

    assert result["customer_id"] == "customer-123"
    assert result["environment"] == "test"
    assert "metadata" not in result["ls_invocation_params"]


def test_infer_invocation_params_protects_langsmith_metadata():
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {
            "model": "gpt-4o-mini",
            "metadata": {
                "ls_provider": "other",
                "ls_model_name": "other-model",
            },
        },
    )

    assert result["ls_provider"] == "openai"
    assert result["ls_model_name"] == "gpt-4o-mini"


@pytest.mark.parametrize("metadata", [None, "invalid", ["invalid"]])
def test_infer_invocation_params_ignores_non_mapping_metadata(metadata):
    result = _infer_invocation_params(
        "chat",
        "openai",
        {},
        False,
        {"model": "gpt-4o-mini", "metadata": metadata},
    )

    assert result["ls_provider"] == "openai"
    assert result["ls_model_name"] == "gpt-4o-mini"


class TestIsAsyncOrWrapsAsync:
    """Verify _is_async_or_wraps_async walks the __wrapped__ chain correctly."""

    def test_direct_async_function(self):
        async def fn():
            pass

        assert _is_async_or_wraps_async(fn) is True

    def test_direct_sync_function(self):
        def fn():
            pass

        assert _is_async_or_wraps_async(fn) is False

    def test_sync_wrapper_over_async_via_functools_wraps(self):
        """functools.wraps sets __wrapped__; chain-walk should detect the async ancestor."""

        async def original():
            pass

        @functools.wraps(original)
        def sync_wrapper(*args, **kwargs):
            return original(*args, **kwargs)

        assert _is_async_or_wraps_async(sync_wrapper) is True

    def test_sync_wrapper_over_sync_function(self):
        def original():
            pass

        @functools.wraps(original)
        def sync_wrapper(*args, **kwargs):
            return original(*args, **kwargs)

        assert _is_async_or_wraps_async(sync_wrapper) is False

    def test_deep_chain_finds_async_ancestor(self):
        async def base():
            pass

        @functools.wraps(base)
        def mid(*args, **kwargs):
            return base(*args, **kwargs)

        @functools.wraps(mid)
        def outer(*args, **kwargs):
            return mid(*args, **kwargs)

        assert _is_async_or_wraps_async(outer) is True

    def test_cycle_guard(self):
        """A __wrapped__ cycle should not infinite-loop."""

        def fn():
            pass

        fn.__wrapped__ = fn  # type: ignore[attr-defined]
        assert _is_async_or_wraps_async(fn) is False


class TestGetWrapperOtelInterop:
    """Verify _get_wrapper selects the async path when OTel hides async behind a sync closure."""

    def test_returns_async_wrapper_for_otel_style_sync_over_async(self):
        async def original_async():
            return {"output": "hello"}

        @functools.wraps(original_async)
        def otel_sync_wrapper(*args, **kwargs):
            return original_async(*args, **kwargs)

        wrapper = _get_wrapper(otel_sync_wrapper, "ChatOpenAI", _reduce_chat)
        assert asyncio.iscoroutinefunction(wrapper), (
            "_get_wrapper must return an async callable when the chain contains an async ancestor"
        )

    def test_otel_style_wrapper_returns_real_result_not_coroutine(self):
        """End-to-end: the async wrapper should await the coroutine, not return it raw."""

        async def original_async():
            return {"output": "awaited"}

        @functools.wraps(original_async)
        def otel_sync_wrapper(*args, **kwargs):
            return original_async(*args, **kwargs)

        wrapper = _get_wrapper(otel_sync_wrapper, "ChatOpenAI", _reduce_chat)

        import unittest.mock as mock

        with mock.patch("langsmith.utils.tracing_is_enabled", return_value=False):
            result = asyncio.run(wrapper())

        assert result == {"output": "awaited"}, (
            "async wrapper must return the awaited result, not a coroutine object"
        )

    def test_returns_sync_wrapper_for_plain_sync_function(self):
        def original_sync():
            return {"output": "sync"}

        wrapper = _get_wrapper(original_sync, "ChatOpenAI", _reduce_chat)
        assert not asyncio.iscoroutinefunction(wrapper)
