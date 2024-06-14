import json
from typing import Optional, Sequence, List
from typing import TypedDict
from unittest.mock import MagicMock

import pytest

from langsmith import traceable
from langsmith.client import Client
from langsmith.run_helpers import tracing_context


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


def _extract_run_information(mock_client: Client) -> List[Request]:
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


def _extract_lineage_information(requests: Sequence[Request]):
    lineages: List[Lineage] = []
    for request in requests:
        if request["verb"] != "POST":
            continue
        if request["path"].endswith("/runs/batch)"):
            continue
        post_data = request["data"]["post"]
        for item in post_data:
            lineages.append(
                {
                    "id": item["id"],
                    "parent_id": item.get("parent_run_id"),
                    "name": item["name"],
                }
            )
    return lineages


class Lineage(TypedDict):
    id: str
    parent_id: Optional[str]
    name: str


def test_foo(mock_client: Client) -> None:
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

    import time

    while not mock_client.tracing_queue.empty():
        time.sleep(0.1)

    calls = _extract_run_information(mock_client)
    calls = _extract_lineage_information(calls)
    assert calls == []
