import asyncio
from concurrent import futures
from unittest.mock import MagicMock

import pytest

from langsmith import Client
from langsmith import traceable
from langsmith.run_helpers import tracing_context, get_current_run_tree
from tests.interop_tracing.utils import extract_span_tree, extract_spans


def _get_mock_client() -> Client:
    mock_session = MagicMock()
    client = Client(session=mock_session, api_key="test")
    return client


@pytest.fixture
def mock_client() -> Client:
    return _get_mock_client()


def test_simple_lineage(mock_client: Client) -> None:
    """Test that the tracing context is enabled"""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def child(x: int):
            return x

        @traceable(client=mock_client)
        def parent(x: int):
            return child(x + 1)

        @traceable(client=mock_client)
        def grand_parent(x: int):
            return parent(x + 1)

        assert grand_parent(1) == 3

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 3
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["grand_parent", "parent", "child"]


async def test_async_simple_lineage(mock_client: Client) -> None:
    """Test that the tracing context is enabled"""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        async def child(x: int):
            return x

        @traceable(client=mock_client)
        async def parent(x: int):
            return await child(x + 1)

        @traceable(client=mock_client)
        async def grand_parent(x: int):
            return await parent(x + 1)

        assert await grand_parent(1) == 3

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 3
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["grand_parent", "parent", "child"]


@pytest.mark.xfail(reason="Unclear if this is supported.")
async def test_async_sync_simple_lineage(mock_client: Client) -> None:
    """Test invoking sync code from async and vice versa."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        async def child(x: int):
            return x

        @traceable(client=mock_client)
        def parent(x: int):
            # Invoke on a separate thread

            with futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, child(x + 1))
                return future.result()

        @traceable(client=mock_client)
        async def grand_parent(x: int):
            return parent(x + 1)

        assert await grand_parent(1) == 3

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 3
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["grand_parent", "parent", "child"]


async def test_async_sync_simple_lineage_with_parent(mock_client: Client) -> None:
    """Test invoking sync code from async and vice versa."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        async def child(x: int):
            return x

        @traceable(client=mock_client)
        def parent(x: int):
            # Invoke on a separate thread
            rt = get_current_run_tree()
            with futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, child(x + 1, langsmith_extra={"parent": rt})
                )
                return future.result()

        @traceable(client=mock_client)
        async def grand_parent(x: int):
            return parent(x + 1)

        assert await grand_parent(1) == 3

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 3
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["grand_parent", "parent", "child"]


def test_recursive_depth_10(mock_client: Client) -> None:
    """Test recursive invocation."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def recursive(x: int):
            if x == 0:
                return 0
            return recursive(x - 1)

        assert recursive(10) == 0

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 11
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["recursive"] * 11


async def test_async_recursive_depth_10(mock_client: Client) -> None:
    """Test recursive invocation."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        async def recursive(x: int):
            if x == 0:
                return 0
            return await recursive(x - 1)

        assert await recursive(10) == 0

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 11
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["recursive"] * 11


def test_fibonacci(mock_client: Client) -> None:
    """Test recursive invocation."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def fib(n: int):
            if n <= 1:
                return n
            return fib(n - 1) + fib(n - 2)

        assert fib(10) == 55

    tree = extract_span_tree(mock_client)
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 177
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["fib"] * 177


async def test_async_fibonacci(mock_client: Client) -> None:
    """Test recursive invocation."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        async def fib(n: int):
            if n <= 1:
                return n
            return await fib(n - 1) + await fib(n - 2)

        assert await fib(10) == 55

    tree = extract_span_tree(mock_client)
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 177
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["fib"] * 177


async def test_mixed_sync_async_fibonacci(mock_client: Client) -> None:
    """Test recursive invocation."""
    with tracing_context(enabled=True):

        @traceable(client=mock_client)
        def sync_fib(n: int):
            if n <= 1:
                return n
            return sync_fib(n - 1) + sync_fib(n - 2)

        @traceable(client=mock_client)
        async def fib(n: int):
            if n <= 1:
                return n
            return await fib(n - 1) + sync_fib(n - 2)

        assert await fib(10) == 55

    tree = extract_span_tree(mock_client)
    sorted_spans = tree.get_breadth_first_traversal()
    assert len(sorted_spans) == 177


@pytest.mark.xfail(reason="The @traceable and RunnableLambda dont play nice")
async def test_tracing_within_runnables() -> None:
    from langchain_core.runnables import RunnableLambda
    from langchain_core.tracers import LangChainTracer

    mock_client = _get_mock_client()

    tracer = LangChainTracer(client=mock_client)

    with tracing_context(enabled=True):

        @traceable()
        def foo(x: int):
            return x + 1

        @traceable()
        def bar(x: int):
            return foo(x + 1)

        bar_ = RunnableLambda(bar)
        assert bar_.invoke(1, {"callbacks": [tracer]}) == 3
    assert extract_spans(mock_client) != [], # Fails here silently
