from unittest.mock import MagicMock

import pytest

from langsmith import Client
from langsmith import traceable
from langsmith.run_helpers import tracing_context
from tests.combined_tracing.utils import extract_span_tree


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

        assert parent(1) == 2

    tree = extract_span_tree(mock_client)
    assert len(tree.get_root_nodes()) == 1
    sorted_spans = tree.get_breadth_first_travel()
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
    sorted_spans = tree.get_breadth_first_travel()
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
    sorted_spans = tree.get_breadth_first_travel()
    assert len(sorted_spans) == 11
    names = [span["name"] for span, _ in sorted_spans]
    assert names == ["recursive"] * 11


async def test_interop(mock_client: Client) -> None:
    """Test interop of sync and async functions."""
