"""Tests for langsmith runtime overrides."""

import contextvars

import pytest

import langsmith
from langsmith._internal import _aiter as aitertools
from langsmith._runtime_overrides import (
    RuntimeOverrides,
    get_runtime_overrides,
    set_runtime_overrides,
)


@pytest.fixture(autouse=True)
def reset_overrides():
    set_runtime_overrides()
    yield
    set_runtime_overrides()


async def test_default_aio_to_thread_runs_in_executor():
    """Without any override, aio_to_thread should run func in a thread."""
    import threading

    main_thread_id = threading.get_ident()
    captured_thread_id = None

    def sync_func(x):
        nonlocal captured_thread_id
        captured_thread_id = threading.get_ident()
        return x * 2

    result = await aitertools.aio_to_thread(contextvars.copy_context(), sync_func, 5)
    assert result == 10
    assert captured_thread_id is not None
    assert captured_thread_id != main_thread_id


async def test_override_is_invoked():
    """When an override is set, it should be called instead of the default."""
    calls = []

    async def my_override(ctx, func, /, *args, **kwargs):
        calls.append((ctx, func, args, kwargs))
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)

    def sync_func(x, y=1):
        return x + y

    ctx = contextvars.copy_context()
    result = await aitertools.aio_to_thread(ctx, sync_func, 5, y=3)
    assert result == 8
    assert len(calls) == 1
    assert calls[0][0] is ctx
    assert calls[0][1] is sync_func
    assert calls[0][2] == (5,)
    assert calls[0][3] == {"y": 3}


async def test_override_does_not_use_run_in_executor():
    """Override should run in the calling thread (for runtimes like Temporal)."""
    import threading

    main_thread_id = threading.get_ident()
    captured_thread_id = None

    async def my_override(ctx, func, /, *args, **kwargs):
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)

    def sync_func(x):
        nonlocal captured_thread_id
        captured_thread_id = threading.get_ident()
        return x * 2

    result = await aitertools.aio_to_thread(contextvars.copy_context(), sync_func, 5)
    assert result == 10
    assert captured_thread_id == main_thread_id


async def test_override_receives_explicit_ctx():
    """Override should receive the Context passed through aio_to_thread."""
    received_ctx = None

    async def my_override(ctx, func, /, *args, **kwargs):
        nonlocal received_ctx
        received_ctx = ctx
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)

    ctx = contextvars.copy_context()

    def sync_func():
        return "ok"

    await aitertools.aio_to_thread(ctx, sync_func)
    assert received_ctx is ctx


async def test_reset_to_default():
    """Calling set_runtime_overrides() with no args resets to defaults."""

    async def my_override(ctx, func, /, *args, **kwargs):
        return "overridden"

    set_runtime_overrides(aio_to_thread=my_override)
    result = await aitertools.aio_to_thread(contextvars.copy_context(), lambda: "x")
    assert result == "overridden"

    set_runtime_overrides()
    result = await aitertools.aio_to_thread(contextvars.copy_context(), lambda: "x")
    assert result == "x"


async def test_override_propagates_exceptions():
    """Exceptions from the override should propagate."""

    class MyError(Exception):
        pass

    async def my_override(ctx, func, /, *args, **kwargs):
        raise MyError("boom")

    set_runtime_overrides(aio_to_thread=my_override)

    with pytest.raises(MyError, match="boom"):
        await aitertools.aio_to_thread(contextvars.copy_context(), lambda: "never")


def test_get_runtime_overrides_returns_instance():
    overrides = get_runtime_overrides()
    assert isinstance(overrides, RuntimeOverrides)
    assert overrides.aio_to_thread is None


def test_set_runtime_overrides_updates_instance():
    async def my_override(ctx, func, /, *args, **kwargs):
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)
    overrides = get_runtime_overrides()
    assert overrides.aio_to_thread is my_override


def test_set_runtime_overrides_exposed_at_top_level():
    assert langsmith.set_runtime_overrides is set_runtime_overrides


async def test_async_trace_context_propagates_under_override():
    """End-to-end: with an override registered, async trace() still propagates
    tracing context — i.e. the override's ctx.run invocation, plus the
    run_helpers fallback that re-applies tracing state from ctx, together
    produce correct parent/child linkage inside an async context manager."""
    from langsmith import get_current_run_tree, trace, tracing_context

    async def my_override(ctx, func, /, *args, **kwargs):
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)

    with tracing_context(enabled="local"):
        assert get_current_run_tree() is None
        async with trace(name="outer", inputs={"step": "outer"}) as outer:
            assert get_current_run_tree() is not None
            assert get_current_run_tree().id == outer.id
            async with trace(name="inner", inputs={"step": "inner"}) as inner:
                assert get_current_run_tree() is not None
                assert get_current_run_tree().id == inner.id
                assert inner.parent_run_id == outer.id
            assert get_current_run_tree().id == outer.id
        assert get_current_run_tree() is None


async def test_traceable_uses_override():
    """A traceable async function should route through the override."""
    from unittest.mock import MagicMock

    from langsmith import traceable

    override_calls = 0

    async def my_override(ctx, func, /, *args, **kwargs):
        nonlocal override_calls
        override_calls += 1
        return ctx.run(func, *args, **kwargs)

    set_runtime_overrides(aio_to_thread=my_override)

    mock_client = MagicMock()
    mock_client.tracing_queue = None

    @traceable(client=mock_client)
    async def my_async_fn(x: int) -> int:
        return x + 1

    with langsmith.tracing_context(enabled=True):
        result = await my_async_fn(1)

    assert result == 2
    assert override_calls > 0
