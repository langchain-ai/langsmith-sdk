import json
import time
import uuid

from collections import deque
from typing import TypedDict, List, Sequence, Optional, Tuple, Any, Dict, Union
from unittest.mock import MagicMock

import pytest

from langsmith import Client


def _get_mock_client() -> Client:
    mock_session = MagicMock()
    client = Client(session=mock_session, api_key="test")
    return client


@pytest.fixture
def mock_client() -> Client:
    return _get_mock_client()


class Request(TypedDict):
    verb: str
    data: dict
    headers: dict
    path: str


def _extract_requests(mock_client: Client) -> List[Request]:
    """Extract run information from the create run calls"""
    calls = []
    for call in mock_client.session.request.mock_calls:
        if not call.args:
            continue

        if not len(call.args) == 2:
            continue

        verb = call.args[0]
        path = call.args[1]
        kwargs = call.kwargs

        if "data" in call.kwargs:
            kwargs = call.kwargs
            kwargs["data"] = json.loads(kwargs["data"])

        calls.append(
            {
                "verb": verb,
                "path": path,
                **kwargs,
            }
        )

    return calls


class Span(TypedDict, total=False):
    """Tracing span."""

    id: str
    parent_id: Optional[str]
    name: str


def _extract_lineage_information(requests: Sequence[Request]) -> List[Span]:
    spans: List[Span] = []
    for request in requests:
        if request["verb"] != "POST":
            continue
        if not request["path"].endswith("/runs/batch"):
            raise ValueError(f"Unrecognized path {request['path']}")
        post_data = request["data"]["post"]
        for item in post_data:
            spans.append(
                {
                    "id": item["id"],
                    "parent_id": item.get("parent_run_id"),
                    "name": item["name"],
                    "tags": item.get("tags", []),
                    "metadata": item.get("metadata", {}),
                    "run_type": item.get("run_type"),
                    "inputs": item.get("inputs"),
                    "outputs": item.get("outputs"),
                }
            )
    return spans


def extract_spans(mock_client: Client) -> List[Span]:
    mock_client.tracing_queue.join()
    calls = _extract_requests(mock_client)
    return _extract_lineage_information(calls)


class SpanTree:
    def __init__(self, spans: List[Span]) -> None:
        """Build a span tree from the spans."""
        for span in spans:
            assert_is_valid_span(span)
        self.spans = spans

        # assert no duplicate ids
        ids = [node["id"] for node in spans]
        assert len(ids) == len(set(ids)), "Duplicate ids found"

        self.child_id_to_parent_id = {node["id"]: node["parent_id"] for node in spans}
        # Invert to calculate parent id to child id
        self.parent_id_to_child_ids = {}
        for child_id, parent_id in self.child_id_to_parent_id.items():
            if parent_id not in self.parent_id_to_child_ids:
                self.parent_id_to_child_ids[parent_id] = []
            self.parent_id_to_child_ids[parent_id].append(child_id)
        self.assert_no_cycles()

    def assert_no_cycles(self) -> None:
        """Assert that the tree has no cycles."""
        # Start from root node
        root_nodes = self.get_root_nodes()
        # Assert only one root node
        assert len(root_nodes) == 1
        root_node = root_nodes[0]
        visited = set()
        stack = [root_node]
        while stack:
            node = stack.pop()
            if node["id"] in visited:
                raise ValueError("Cycle detected")
            visited.add(node["id"])
            children = self.get_children(node)
            stack.extend(children)

    def get_root_nodes(self) -> List[Span]:
        """Return all nodes that do not have a parent."""
        return [node for node in self.spans if node["parent_id"] is None]

    def get_children(self, node: Span) -> List[Span]:
        """Return all nodes that have the given node as a parent."""
        child_ids = self.parent_id_to_child_ids.get(node["id"], [])
        return [child for child in self.spans if child["id"] in child_ids]

    def get_breadth_first_traversal(
        self, *, include_level: bool = False
    ) -> Union[List[Tuple[Span, int]], List[Span]]:
        """Return a list of nodes in the order they were added."""
        # First we assert there's only a single root node
        root_nodes = self.get_root_nodes()
        root_node = root_nodes[0]
        # Then we create a list to hold the nodes
        nodes_and_level = []
        # Then we create a queue to hold the nodes we need to visit

        # Track of node and its level
        queue = deque([(root_node, 0)])
        # While there are nodes to visit
        while queue:
            # Pop the first node from the queue
            node, level = queue.popleft()
            # Add the node to the list
            nodes_and_level.append((node, level))
            # Get the children of the node
            children = self.get_children(node)
            # Add the children to the queue
            for child in children:
                queue.append((child, level + 1))
        return nodes_and_level


def extract_span_tree(mock_client: Client) -> SpanTree:
    spans = extract_spans(mock_client)
    return SpanTree(spans)


def assert_is_valid_span(span: Span):
    """Assert that the span is valid."""
    assert isinstance(span["id"], str)
    try:
        uuid.UUID(span["id"])
    except ValueError:
        raise AssertionError(f"Invalid span id {span['id']}, should be a UUID")
    assert isinstance(span["name"], str)

    if span.get("parent_id") is not None:
        assert isinstance(span["parent_id"], str)
        try:
            uuid.UUID(span["parent_id"])
        except ValueError:
            raise AssertionError(
                f"Invalid parent id {span['parent_id']}, should be a UUID"
            )

    assert isinstance(span.get("tags", []), list)
    assert isinstance(span.get("metadata", {}), dict)
    assert span.get("inputs") is not None, f"Span should have inputs. {span}"

