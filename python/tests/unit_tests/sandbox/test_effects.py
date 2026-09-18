"""Tests for the inline sync/async effect interpreter."""

import asyncio
from collections.abc import Generator
from typing import Any

import pytest

from langsmith.sandbox._effects import Call, run_async, run_sync


def program(call, events):
    try:
        first = yield from Call(call)
        second = yield from Call(lambda: first + 1)
        return second
    finally:
        events.append("closed")


def immediate() -> Generator[Call[Any], Any, int]:
    return 42
    yield


def recover(call, events):
    try:
        yield from Call(call)
    except ValueError:
        return (yield from Call(lambda: "recovered"))
    finally:
        events.append("closed")


def fail():
    raise ValueError("failure")


def test_sync_execution_is_lazy_and_composable():
    events = []
    effect = program(lambda: 41, events)
    assert events == []
    assert run_sync(effect) == 42
    assert events == ["closed"]
    assert run_sync(immediate()) == 42
    assert run_sync(recover(fail, events)) == "recovered"
    with pytest.raises(ValueError, match="failure"):
        run_sync(program(fail, events))
    assert events == ["closed"] * 3


@pytest.mark.asyncio
async def test_async_execution_handles_sync_and_async_calls():
    async def value():
        await asyncio.sleep(0)
        return 41

    async def failure():
        await asyncio.sleep(0)
        fail()

    events = []
    assert await run_async(program(value, events)) == 42
    assert await run_async(program(lambda: 41, events)) == 42
    assert await run_async(immediate()) == 42
    assert await run_async(recover(failure, events)) == "recovered"
    with pytest.raises(ValueError, match="failure"):
        await run_async(program(failure, events))
    assert events == ["closed"] * 4


def test_sync_rejects_and_closes_coroutines():
    async def value():
        return 41

    coroutine = value()
    events = []
    with pytest.raises(TypeError, match="cannot resolve an awaitable"):
        run_sync(program(lambda: coroutine, events))
    assert coroutine.cr_frame is None
    assert events == ["closed"]


@pytest.mark.asyncio
async def test_cancellation_runs_effectful_cleanup():
    entered = asyncio.Event()
    events = []

    async def wait():
        entered.set()
        await asyncio.Event().wait()

    async def cleanup():
        await asyncio.sleep(0)
        events.append("closed")

    def effect():
        try:
            yield from Call(wait)
        finally:
            yield from Call(cleanup)

    task = asyncio.create_task(run_async(effect()))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["closed"]
