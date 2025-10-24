import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from langsmith import run_trees
from langsmith.client import Client
from langsmith.run_trees import RunTree


def test_run_tree_accepts_tpe() -> None:
    mock_client = MagicMock(spec=Client)
    run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        client=mock_client,
        executor=ThreadPoolExecutor(),  # type: ignore
    )


def test_lazy_rt() -> None:
    run_tree = RunTree(name="foo")
    assert run_tree.ls_client is None
    assert run_tree._client is None
    assert isinstance(run_tree.client, Client)
    client = Client(api_key="foo")
    run_tree._client = client
    assert run_tree._client == client

    assert RunTree(name="foo", client=client).client == client
    assert RunTree(name="foo", ls_client=client).client == client


def test_json_serializable():
    run_tree = RunTree(name="foo")
    d = run_tree.dict()
    assert not d.get("client") and not d.get("ls_client")
    assert isinstance(run_tree.client, Client)
    d = run_tree.dict()
    assert not d.get("client") and not d.get("ls_client")
    d = json.loads(run_tree.json())
    assert not d.get("client") and not d.get("ls_client")
    run_tree = RunTree(name="foo", ls_client=Client())
    d = run_tree.dict()
    assert not d.get("client") and not d.get("ls_client")
    d = json.loads(run_tree.json())
    assert not d.get("client") and not d.get("ls_client")
    run_tree = RunTree(name="foo", client=Client())
    d = run_tree.dict()
    assert not d.get("client") and not d.get("ls_client")
    d = json.loads(run_tree.json())
    assert not d.get("client") and not d.get("ls_client")


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (
            "20240412T202937370454Z152ce25c-064e-4742-bf36-8bb0389f8805.20240412T202937627763Zfe8b541f-e75a-4ee6-b92d-732710897194.20240412T202937708023Z625b30ed-2fbb-4387-81b1-cb5d6221e5b4.20240412T202937775748Z448dc09f-ad54-4475-b3a4-fa43018ca621.20240412T202937981350Z4cd59ea4-491e-4ed9-923f-48cd93e03755.20240412T202938078862Zcd168cf7-ee72-48c2-8ec0-50ab09821973.20240412T202938152278Z32481c1a-b83c-4b53-a52e-1ea893ffba51",
            [
                (
                    datetime(2024, 4, 12, 20, 29, 37, 370454),
                    UUID("152ce25c-064e-4742-bf36-8bb0389f8805"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 627763),
                    UUID("fe8b541f-e75a-4ee6-b92d-732710897194"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 708023),
                    UUID("625b30ed-2fbb-4387-81b1-cb5d6221e5b4"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 775748),
                    UUID("448dc09f-ad54-4475-b3a4-fa43018ca621"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 37, 981350),
                    UUID("4cd59ea4-491e-4ed9-923f-48cd93e03755"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 38, 78862),
                    UUID("cd168cf7-ee72-48c2-8ec0-50ab09821973"),
                ),
                (
                    datetime(2024, 4, 12, 20, 29, 38, 152278),
                    UUID("32481c1a-b83c-4b53-a52e-1ea893ffba51"),
                ),
            ],
        ),
    ],
)
def test_parse_dotted_order(inputs, expected):
    assert run_trees._parse_dotted_order(inputs) == expected


def test_run_tree_events_not_null():
    mock_client = MagicMock(spec=Client)
    run_tree = run_trees.RunTree(
        name="My Chat Bot",
        inputs={"text": "Summarize this morning's meetings."},
        client=mock_client,
        events=None,
    )
    assert run_tree.events == []


def test_nested_run_trees_from_dotted_order():
    grandparent = run_trees.RunTree(
        name="Grandparent",
        inputs={"text": "Summarize this morning's meetings."},
        client=MagicMock(spec=Client),
    )
    parent = grandparent.create_child(
        name="Parent",
    )
    child = parent.create_child(
        name="Child",
    )
    # Check child
    clone = run_trees.RunTree.from_dotted_order(
        dotted_order=child.dotted_order,
        name="Clone",
        client=MagicMock(spec=Client),
    )

    assert clone.id == child.id
    assert clone.parent_run_id == child.parent_run_id
    assert clone.dotted_order == child.dotted_order

    # Check parent
    parent_clone = run_trees.RunTree.from_dotted_order(
        dotted_order=parent.dotted_order,
        name="Parent Clone",
        client=MagicMock(spec=Client),
    )
    assert parent_clone.id == parent.id
    assert parent_clone.parent_run_id == parent.parent_run_id
    assert parent_clone.dotted_order == parent.dotted_order

    # Check grandparent
    grandparent_clone = run_trees.RunTree.from_dotted_order(
        dotted_order=grandparent.dotted_order,
        name="Grandparent Clone",
        client=MagicMock(spec=Client),
    )
    assert grandparent_clone.id == grandparent.id
    assert grandparent_clone.parent_run_id is None
    assert grandparent_clone.dotted_order == grandparent.dotted_order


def test_distributed_tracing_slice_parent_id():
    """Test distributed tracing functionality with _slice_parent_id method."""
    mock_client = MagicMock(spec=Client)

    grandparent = RunTree(
        name="Grandparent",
        inputs={"text": "root"},
        client=mock_client,
    )
    parent = grandparent.create_child(name="Parent")
    child = parent.create_child(name="Child")

    parent_id = str(parent.id)

    child_dict = child._get_dicts_safe()

    assert child_dict["parent_run_id"] == parent.id
    assert child_dict["trace_id"] == grandparent.id
    assert child_dict["dotted_order"] is not None

    child._slice_parent_id(parent_id, child_dict)

    assert child_dict.get("parent_run_id") is None
    assert child_dict["trace_id"] == child.id

    parsed_order = run_trees._parse_dotted_order(child_dict["dotted_order"])
    assert len(parsed_order) == 1
    assert parsed_order[0][1] == child.id


def test_distributed_tracing_remap_for_project():
    """Test distributed tracing with _remap_for_project method."""
    mock_client = MagicMock(spec=Client)

    grandparent = RunTree(
        name="Grandparent",
        inputs={"text": "root"},
        client=mock_client,
        session_name="original_project",
    )
    parent = grandparent.create_child(name="Parent")
    child = parent.create_child(name="Child")

    parent_id = str(parent.id)
    run_trees._DISTRIBUTED_PARENT_ID.set(parent_id)

    try:
        updates = {"reroot": True}
        remapped_dict = child._remap_for_project("child_project", updates)

        assert remapped_dict.get("parent_run_id") is None
        assert remapped_dict["session_name"] == "child_project"

        parsed_order = run_trees._parse_dotted_order(remapped_dict["dotted_order"])
        assert len(parsed_order) == 1

        updates_no_dist = {"reroot": False}
        remapped_dict_no_dist = child._remap_for_project(
            "child_project_2", updates_no_dist
        )
        assert remapped_dict_no_dist.get("parent_run_id") is not None
        remapped_dict_no_updates = child._remap_for_project("child_project_3", None)

        assert remapped_dict_no_updates.get("parent_run_id") is not None

    finally:
        run_trees._DISTRIBUTED_PARENT_ID.set(None)


def test_distributed_parent_id_from_headers():
    """Test that _DISTRIBUTED_PARENT_ID is correctly set directly in from_headers()."""
    mock_client = MagicMock(spec=Client)

    # Create a hierarchy: grandparent -> parent -> child
    grandparent = RunTree(
        name="Grandparent",
        inputs={"text": "grandparent"},
        client=mock_client,
        session_name="original_project",
    )
    parent = grandparent.create_child(name="Parent")
    child = parent.create_child(name="Child")

    headers = child.to_headers()

    RunTree.from_headers(headers)

    current_distributed_parent_id = run_trees._DISTRIBUTED_PARENT_ID.get()

    new_run = RunTree(
        name="NewRun",
        inputs={"text": "new_run"},
        client=mock_client,
        session_name="child_project",
    )

    remapped_dict = new_run._remap_for_project("child_project", {"reroot": True})

    assert remapped_dict.get("parent_run_id") is None, (
        "Run should be rerooted with no parent"
    )

    parsed_order = run_trees._parse_dotted_order(remapped_dict["dotted_order"])
    assert len(parsed_order) == 1, (
        f"Expected 1 segment after rerooting, got {len(parsed_order)}"
    )

    assert remapped_dict["trace_id"] == new_run.id, (
        "Trace ID should be the new run's ID after rerooting"
    )

    assert str(current_distributed_parent_id) == str(child.id), (
        f"Distributed parent ID should be the immediate parent from headers! "
        f"Expected {child.id}, got {current_distributed_parent_id}"
    )
