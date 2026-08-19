"""Benchmarks for the `@traceable` decorator.

`@traceable` is the most widely used entry point of the SDK and it wraps user
functions directly, so the wrapper's overhead is added to every decorated call.
The comparison against the undecorated function makes that overhead visible.
"""

import asyncio

from langsmith.client import Client
from langsmith.run_helpers import traceable, tracing_context
from tests.benchmarks._payloads import mock_session


def _client() -> Client:
    return Client(session=mock_session(), api_key="fake", auto_batch_tracing=False)


def _plain(a: int, b: int, **kwargs) -> dict:
    return {"result": a + b, "kwargs": kwargs}


def test_traceable_sync_call(benchmark):
    client = _client()
    traced = traceable(client=client)(_plain)

    def run() -> None:
        with tracing_context(enabled=True):
            for _ in range(20):
                traced(1, 2, c="hello")

    benchmark(run)


def test_traceable_disabled_call(benchmark):
    """Overhead of the wrapper when tracing is turned off."""
    client = _client()
    traced = traceable(client=client)(_plain)

    def run() -> None:
        with tracing_context(enabled=False):
            for _ in range(20):
                traced(1, 2, c="hello")

    benchmark(run)


def test_traceable_nested_calls(benchmark):
    """A parent span with children, i.e. the usual application shape."""
    client = _client()

    @traceable(client=client)
    def child(i: int) -> int:
        return i * 2

    @traceable(client=client)
    def parent(n: int) -> int:
        return sum(child(i) for i in range(n))

    def run() -> None:
        with tracing_context(enabled=True):
            parent(10)

    benchmark(run)


def test_traceable_async_call(benchmark):
    client = _client()

    @traceable(client=client)
    async def traced(a: int, b: int) -> int:
        return a + b

    async def run_many() -> None:
        with tracing_context(enabled=True):
            for _ in range(20):
                await traced(1, 2)

    loop = asyncio.new_event_loop()
    try:
        benchmark(lambda: loop.run_until_complete(run_many()))
    finally:
        loop.close()
