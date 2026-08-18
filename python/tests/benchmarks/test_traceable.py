"""Benchmarks for the `@traceable` decorator.

`@traceable` wraps user code, so its overhead is paid on every call of an
instrumented function. These benchmarks measure the decorator overhead for flat
and nested call trees, both sync and async.
"""

import asyncio

import pytest

from langsmith import traceable
from langsmith.run_trees import RunTree


@traceable
def _traced_leaf(x: int) -> int:
    return x + 1


@traceable
def _traced_parent(x: int) -> int:
    total = 0
    for i in range(5):
        total += _traced_leaf(x + i)
    return total


@traceable
async def _traced_async_leaf(x: int) -> int:
    return x + 1


@pytest.mark.benchmark
def test_traceable_flat_calls(benchmark, client):
    def run() -> None:
        for i in range(200):
            _traced_leaf(i, langsmith_extra={"client": client})

    benchmark(run)


@pytest.mark.benchmark
def test_traceable_nested_calls(benchmark, client):
    def run() -> None:
        for i in range(50):
            _traced_parent(i, langsmith_extra={"client": client})

    benchmark(run)


@pytest.mark.benchmark
def test_traceable_with_explicit_parent(benchmark, client):
    def run() -> None:
        parent = RunTree(name="parent", ls_client=client)
        for i in range(100):
            _traced_leaf(i, langsmith_extra={"parent": parent, "client": client})

    benchmark(run)


@pytest.mark.benchmark
def test_traceable_async_calls(benchmark, client):
    async def run_async() -> None:
        for i in range(200):
            await _traced_async_leaf(i, langsmith_extra={"client": client})

    def run() -> None:
        asyncio.run(run_async())

    benchmark(run)
