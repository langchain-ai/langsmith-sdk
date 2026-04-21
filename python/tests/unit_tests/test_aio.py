"""Unit tests for langsmith.aio."""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from langsmith._internal import _aiter as aitertools
from langsmith.aio import (
    TracingCall,
    get_loop_sync_runner,
    set_loop_sync_runner,
)


def _double_sync(x):
    return x * 2


async def test_default_uses_run_in_executor():
    loop = asyncio.get_running_loop()
    assert get_loop_sync_runner(loop) is None
    result = await aitertools.aio_to_thread(_double_sync, 21)
    assert result == 42


async def test_runner_receives_tracing_call():
    loop = asyncio.get_running_loop()
    received: list[TracingCall] = []

    async def runner(call: TracingCall):
        received.append(call)
        return call.op()

    set_loop_sync_runner(loop, runner)
    try:
        result = await aitertools.aio_to_thread(_double_sync, 21)
    finally:
        set_loop_sync_runner(loop, None)

    assert result == 42
    assert len(received) == 1
    call = received[0]
    assert call.func is _double_sync
    assert call.args == (21,)
    assert call.kwargs == {}
    assert isinstance(call.context, contextvars.Context)


async def test_runner_can_use_raw_form():
    """Temporal-style: bypass ctx.run so contextvar mutations propagate."""
    loop = asyncio.get_running_loop()

    async def raw_runner(call: TracingCall):
        return call.func(*call.args, **call.kwargs)

    set_loop_sync_runner(loop, raw_runner)
    try:
        result = await aitertools.aio_to_thread(_double_sync, 10)
    finally:
        set_loop_sync_runner(loop, None)
    assert result == 20


async def test_unregister_with_none():
    loop = asyncio.get_running_loop()

    async def runner(call: TracingCall):
        return call.op()

    set_loop_sync_runner(loop, runner)
    assert get_loop_sync_runner(loop) is runner
    set_loop_sync_runner(loop, None)
    assert get_loop_sync_runner(loop) is None
    # unregistering when nothing is set is a no-op
    set_loop_sync_runner(loop, None)
    assert get_loop_sync_runner(loop) is None


async def test_runner_scoped_to_loop_not_process():
    """A runner registered on loop A must not apply to loop B."""
    current = asyncio.get_running_loop()
    other_loop = asyncio.new_event_loop()

    async def runner_for_other(call: TracingCall):
        return call.op()

    set_loop_sync_runner(other_loop, runner_for_other)
    try:
        # Current loop has no runner — default path
        assert get_loop_sync_runner(current) is None
        result = await aitertools.aio_to_thread(_double_sync, 3)
        assert result == 6
    finally:
        set_loop_sync_runner(other_loop, None)
        other_loop.close()


async def test_runner_exception_propagates():
    loop = asyncio.get_running_loop()

    class Boom(RuntimeError):
        pass

    async def raising_runner(call: TracingCall):
        raise Boom("runner refused")

    set_loop_sync_runner(loop, raising_runner)
    try:
        with pytest.raises(Boom, match="refused"):
            await aitertools.aio_to_thread(_double_sync, 1)
    finally:
        set_loop_sync_runner(loop, None)


async def test_callable_exception_propagates_through_runner():
    loop = asyncio.get_running_loop()

    class CallBoom(ValueError):
        pass

    def bad():
        raise CallBoom("nope")

    async def runner(call: TracingCall):
        return call.op()

    set_loop_sync_runner(loop, runner)
    try:
        with pytest.raises(CallBoom, match="nope"):
            await aitertools.aio_to_thread(bad)
    finally:
        set_loop_sync_runner(loop, None)


def test_works_when_loop_rejects_run_in_executor():
    """Custom loop without run_in_executor: runner must bypass it entirely."""

    class NoExecLoop(asyncio.SelectorEventLoop):
        def run_in_executor(self, executor, func, *args):
            raise RuntimeError("run_in_executor is disabled on this loop")

    async def runner(call: TracingCall):
        return call.op()

    loop = NoExecLoop()
    set_loop_sync_runner(loop, runner)
    try:
        result = loop.run_until_complete(aitertools.aio_to_thread(_double_sync, 7))
        assert result == 14
    finally:
        set_loop_sync_runner(loop, None)
        loop.close()


def test_without_runner_loop_that_rejects_executor_raises():
    """Sanity: without a runner, the default path hits the loop's
    run_in_executor and surfaces the loop's error — proving the runner
    really is what unblocks the Temporal-style case."""

    class NoExecLoop(asyncio.SelectorEventLoop):
        def run_in_executor(self, executor, func, *args):
            raise RuntimeError("run_in_executor is disabled on this loop")

    loop = NoExecLoop()
    try:
        with pytest.raises(RuntimeError, match="disabled"):
            loop.run_until_complete(aitertools.aio_to_thread(_double_sync, 7))
    finally:
        loop.close()


async def test_context_propagation_via_op():
    loop = asyncio.get_running_loop()
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="outer")

    def read_var():
        return var.get()

    async def runner(call: TracingCall):
        return call.op()

    var.set("outer-set")
    set_loop_sync_runner(loop, runner)
    try:
        # op runs inside the copied Context; "outer-set" is visible.
        result = await aitertools.aio_to_thread(read_var)
    finally:
        set_loop_sync_runner(loop, None)
    assert result == "outer-set"


async def test_context_propagation_via_raw_func():
    loop = asyncio.get_running_loop()
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var2", default="outer")

    def read_var():
        return var.get()

    async def raw_runner(call: TracingCall):
        return call.func(*call.args, **call.kwargs)

    var.set("also-set")
    set_loop_sync_runner(loop, raw_runner)
    try:
        result = await aitertools.aio_to_thread(read_var)
    finally:
        set_loop_sync_runner(loop, None)
    assert result == "also-set"
