"""Unit tests for the wrap_gemini wrapper function itself."""

import warnings

import pytest

from langsmith._internal._beta_decorator import LangSmithBetaWarning
from langsmith.wrappers._gemini import wrap_gemini


class _MockModels:
    """Sync models namespace, mirrors genai.client.models."""

    def generate_content(self, *args, **kwargs):  # noqa: D102
        pass

    def generate_content_stream(self, *args, **kwargs):  # noqa: D102
        return iter([])


class _MockAioModels:
    """Async models namespace, mirrors genai.client.aio.models."""

    async def generate_content(self, *args, **kwargs):  # noqa: D102
        pass


class _MockGeminiClient:
    """Stand-in for google.genai.Client — no google-genai package required."""

    def __init__(self) -> None:
        self.models = _MockModels()
        # Minimal aio namespace: only .models.generate_content is needed here.
        self.aio = type("_Aio", (), {"models": _MockAioModels()})()


def _wrap(client, **kw):
    """Call wrap_gemini while suppressing the expected beta warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LangSmithBetaWarning)
        return wrap_gemini(client, **kw)


def test_importable_from_langsmith_wrappers():
    # Regression guard: the original issue was AttributeError on this attribute.
    from langsmith import wrappers

    assert hasattr(wrappers, "wrap_gemini")


def test_importable_directly():
    from langsmith.wrappers import wrap_gemini as wg

    assert callable(wg)


def test_in_wrappers_all():
    from langsmith import wrappers

    assert "wrap_gemini" in wrappers.__all__


def test_wraps_sync_generate_content():
    client = _MockGeminiClient()
    original = client.models.generate_content
    _wrap(client)
    assert client.models.generate_content is not original
    # functools.wraps preserves the original callable; supports double-wrap detection.
    assert hasattr(client.models.generate_content, "__wrapped__")


def test_wraps_sync_generate_content_stream():
    client = _MockGeminiClient()
    original = client.models.generate_content_stream
    _wrap(client)
    assert client.models.generate_content_stream is not original
    assert hasattr(client.models.generate_content_stream, "__wrapped__")


def test_wraps_async_generate_content():
    client = _MockGeminiClient()
    original = client.aio.models.generate_content
    _wrap(client)
    assert client.aio.models.generate_content is not original
    assert hasattr(client.aio.models.generate_content, "__wrapped__")


def test_double_wrap_raises():
    client = _MockGeminiClient()
    _wrap(client)
    with pytest.raises(ValueError, match="already been wrapped"):
        _wrap(client)


def test_partial_client_does_not_crash():
    """A client missing aio / stream methods should not raise."""

    class _SyncOnly:
        def __init__(self) -> None:
            self.models = _MockModels()

    client = _SyncOnly()
    result = _wrap(client)
    assert result is client
    assert hasattr(client.models.generate_content, "__wrapped__")


def test_beta_warning_emitted():
    from langsmith._internal._beta_decorator import _warn_once

    # _warn_once is lru_cache'd so it only fires once per process; clear it first.
    _warn_once.cache_clear()
    client = _MockGeminiClient()
    with pytest.warns(LangSmithBetaWarning):
        wrap_gemini(client)
