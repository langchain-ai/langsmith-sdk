"""Unit tests for langsmith.tracing_offload."""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from langsmith._internal import _aiter as aitertools
from langsmith.tracing_offload import (
    TracingCall,
    get_tracing_offload,
    reset_tracing_offload,
    set_tracing_offload,
    tracing_offload,
)


async def _double(x):
    return x * 2


def _double_sync(x):
    return x * 2


async def test_default_uses_run_in_executor():
    result = await aitertools.aio_to_thread(_double_sync, 21)
    assert result == 42
    assert get_tracing_offload() is None


async def test_offload_receives_zero_arg_op():
    received: list[TracingCall] = []

    async def offload(call: TracingCall):
        received.append(call)
        return call.op()

    with tracing_offload(offload):
        result = await aitertools.aio_to_thread(_double_sync, 21)

    assert result == 42
    assert len(received) == 1
    call = received[0]
    assert call.func is _double_sync
    assert call.args == (21,)
    assert call.kwargs == {}
    assert isinstance(call.context, contextvars.Context)


async def test_offload_can_use_raw_form():
    """Temporal-style: bypass ctx.run so contextvar mutations propagate."""

    async def raw_offload(call: TracingCall):
        return call.func(*call.args, **call.kwargs)

    with tracing_offload(raw_offload):
        result = await aitertools.aio_to_thread(_double_sync, 10)
    assert result == 20


async def test_nested_scoping():
    outer_calls = 0
    inner_calls = 0

    async def outer(call: TracingCall):
        nonlocal outer_calls
        outer_calls += 1
        return call.op()

    async def inner(call: TracingCall):
        nonlocal inner_calls
        inner_calls += 1
        return call.op()

    with tracing_offload(outer):
        await aitertools.aio_to_thread(_double_sync, 1)
        assert get_tracing_offload() is outer
        with tracing_offload(inner):
            assert get_tracing_offload() is inner
            await aitertools.aio_to_thread(_double_sync, 1)
        assert get_tracing_offload() is outer
        await aitertools.aio_to_thread(_double_sync, 1)

    assert outer_calls == 2
    assert inner_calls == 1
    assert get_tracing_offload() is None


async def test_offload_inherits_into_tasks_spawned_within_scope():
    """Tasks spawned inside the scope inherit the offload (desired)."""

    async def offload(call: TracingCall):
        return call.op()

    observed: list[object] = []

    async def child():
        observed.append(get_tracing_offload())

    with tracing_offload(offload):
        await asyncio.gather(child())

    assert observed == [offload]


async def test_offload_does_not_leak_to_tasks_spawned_outside_scope():
    """Tasks whose Context was captured before the scope must not see it."""

    async def offload(call: TracingCall):
        return call.op()

    observed: list[object] = []

    async def pre_existing():
        # Wait until the offload is installed in the parent frame,
        # then verify we do not observe it — because our Context was
        # captured at task-creation time, before the `with` block.
        await asyncio.sleep(0)
        observed.append(get_tracing_offload())

    task = asyncio.create_task(pre_existing())
    with tracing_offload(offload):
        await task
    assert observed == [None]


async def test_offload_exception_propagates():
    class Boom(RuntimeError):
        pass

    async def raising_offload(call: TracingCall):
        raise Boom("offload refused to run")

    with tracing_offload(raising_offload):
        with pytest.raises(Boom, match="refused"):
            await aitertools.aio_to_thread(_double_sync, 1)


async def test_callable_exception_propagates_through_offload():
    class CallBoom(ValueError):
        pass

    def bad():
        raise CallBoom("nope")

    async def offload(call: TracingCall):
        return call.op()

    with tracing_offload(offload):
        with pytest.raises(CallBoom, match="nope"):
            await aitertools.aio_to_thread(bad)


async def test_set_reset_imperative_form():
    async def offload(call: TracingCall):
        return call.op()

    assert get_tracing_offload() is None
    token = set_tracing_offload(offload)
    try:
        assert get_tracing_offload() is offload
    finally:
        reset_tracing_offload(token)
    assert get_tracing_offload() is None


async def test_works_when_loop_rejects_run_in_executor():
    """If a custom loop doesn't implement run_in_executor, the offload path
    must not touch it. This guards the Temporal-style case."""

    class _NoExec:
        def run_in_executor(self, *_args, **_kwargs):
            raise RuntimeError("run_in_executor is disabled")

    sentinel = _NoExec()

    async def offload(call: TracingCall):
        return call.op()

    with tracing_offload(offload):
        # Monkey-patch the loop lookup inside aio_to_thread's module scope
        # only for the duration of this call; the offload path should never
        # consult the loop, so this should still succeed.
        orig = aitertools.asyncio.get_running_loop
        aitertools.asyncio.get_running_loop = lambda: sentinel  # type: ignore[assignment]
        try:
            result = await aitertools.aio_to_thread(_double_sync, 3)
        finally:
            aitertools.asyncio.get_running_loop = orig  # type: ignore[assignment]
    assert result == 6


async def test_context_propagation_via_op():
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="outer")

    def read_var():
        return var.get()

    async def offload(call: TracingCall):
        return call.op()

    var.set("outer-set")
    with tracing_offload(offload):
        result = await aitertools.aio_to_thread(read_var)
    # op runs inside the copied Context; the "outer-set" value must be visible.
    assert result == "outer-set"


async def test_context_propagation_via_raw_func():
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var2", default="outer")

    def read_var():
        return var.get()

    async def raw_offload(call: TracingCall):
        return call.func(*call.args, **call.kwargs)

    var.set("also-set")
    with tracing_offload(raw_offload):
        # Raw form uses the ambient context, which still has the value.
        result = await aitertools.aio_to_thread(read_var)
    assert result == "also-set"
