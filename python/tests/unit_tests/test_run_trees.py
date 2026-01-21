import inspect
import io
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from multipart import MultipartParser, parse_options_header
from requests_toolbelt import MultipartEncoder

from langsmith import run_trees
from langsmith import schemas as ls_schemas
from langsmith._internal._uuid import uuid7_deterministic
from langsmith.client import Client
from langsmith.run_trees import NonRecordingRunTree, RunTree


def _get_calls(
    mock_client: Client,
    minimum: int = 0,
    verbs: set[str] = {"POST"},
    attempts: int = 10,
):
    calls = []
    for _ in range(attempts):
        calls = [
            c
            for c in mock_client.session.request.mock_calls  # type: ignore[attr-defined]
            if c.args and c.args[0] in verbs
        ]
        if minimum is None:
            return calls
        if minimum is not None and len(calls) > minimum:
            break
        time.sleep(0.1)
    return calls


def _get_multipart_data(mock_calls):
    datas = []
    for call_ in mock_calls:
        data = call_.kwargs.get("data")
        headers = call_.kwargs.get("headers", {})
        content_type = headers.get("Content-Type")
        if not content_type or not content_type.startswith("multipart/form-data"):
            continue

        # Get boundary from content type
        boundary = parse_options_header(content_type)[1].get("boundary")
        if not boundary:
            continue

        # Normalize data to raw bytes
        if isinstance(data, (bytes, bytearray)):
            raw = data
        elif isinstance(data, MultipartEncoder):
            raw = data.to_string()
        else:
            # Unknown format
            continue

        parser = MultipartParser(io.BytesIO(raw), boundary)
        for part in parser.parts():
            name = part.name
            part_ct = part.headers.get("Content-Type", "")
            value = part.value
            datas.append((name, (part_ct, value)))
    return datas


def _get_mock_client(**kwargs):
    mock_session = MagicMock()
    client = Client(session=mock_session, api_key="test", **kwargs)
    return client


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


def test_remap_for_project():
    """Test _remap_for_project remaps IDs correctly using uuid7_deterministic."""
    mock_client = MagicMock(spec=Client)

    root = RunTree(name="Root", inputs={}, client=mock_client, session_name="original")
    child = root.create_child(name="Child")

    # Same project: no remapping
    same = child._remap_for_project("original")
    assert same["id"] == child.id

    # Different project: IDs remapped deterministically
    r1 = child._remap_for_project("replica")
    r2 = child._remap_for_project("replica")

    assert r1["id"] == uuid7_deterministic(child.id, "replica")
    assert r1["trace_id"] == uuid7_deterministic(root.id, "replica")
    assert r1["parent_run_id"] == uuid7_deterministic(root.id, "replica")
    assert r1["id"].version == 7
    assert r1 == r2  # Deterministic


def test_inputs_attachment_moved_to_attachments():
    """Ensure Attachment values in inputs are moved to attachments."""
    mock_client = _get_mock_client(
        info=ls_schemas.LangSmithInfo(
            instance_flags={
                "zstd_compression_enabled": False,
            },
            batch_ingest_config=ls_schemas.BatchIngestConfig(
                use_multipart_endpoint=True,
                size_limit_bytes=None,
                size_limit=100,
                scale_up_nthreads_limit=16,
                scale_up_qsize_trigger=1000,
                scale_down_nempty_trigger=4,
            ),
        ),
    )
    run_tree = RunTree(
        name="WithAttachment",
        inputs={
            "text": "hello",
            "file": ls_schemas.Attachment(mime_type="text/plain", data=b"hi"),
        },
        client=mock_client,
    )
    run_tree.post()

    # Wait until at least one POST call is recorded by the background thread
    calls = _get_calls(mock_client, minimum=0)
    assert calls
    datas = _get_multipart_data(calls)
    assert datas

    # Find trace_id from a post field
    post_keys = [k for k, _ in datas if k.startswith("post.") and k.endswith(".inputs")]
    assert post_keys, f"No post inputs found in multipart fields: {datas}"
    # Keys are like 'post.<trace_id>.inputs'
    trace_id = post_keys[0].split(".")[1]

    # Verify inputs no longer contain the attachment key
    _, (_, inputs_bytes) = next((d for d in datas if d[0] == f"post.{trace_id}.inputs"))
    inputs_obj = json.loads(inputs_bytes)
    assert inputs_obj == {"text": "hello"}

    # Verify the attachment was uploaded under the correct key
    key = f"attachment.{trace_id}.file"
    _, (mime_type, content) = next((d for d in datas if d[0] == key))
    assert mime_type == "text/plain"
    assert content == "hi"


def test_create_child_enforces_timestamp_order():
    """Test that child runs cannot have start_time earlier than parent.

    This prevents timestamp ordering violations in dotted_order that can
    cause 400 Bad Request errors from the LangSmith API.

    See: https://github.com/langchain-ai/langsmith-sdk/issues/2236
    """
    mock_client = MagicMock(spec=Client)

    # Create a parent run with a specific timestamp
    parent_time = datetime(2025, 12, 22, 23, 43, 8, 14739, tzinfo=timezone.utc)
    parent = RunTree(
        name="Parent",
        start_time=parent_time,
        client=mock_client,
    )

    # Try to create a child with an earlier timestamp (simulating race condition)
    earlier_time = parent_time - timedelta(milliseconds=3)
    child = parent.create_child(
        name="Child",
        start_time=earlier_time,
    )

    # Child's start_time should be adjusted to match parent's start_time
    assert child.start_time == parent.start_time
    assert child.parent_run_id == parent.id

    # Test with a later timestamp - should not be modified
    later_time = parent_time + timedelta(milliseconds=10)
    child2 = parent.create_child(
        name="Child2",
        start_time=later_time,
    )
    assert child2.start_time == later_time

    # Test with no start_time provided - should use current time
    child3 = parent.create_child(name="Child3")
    assert child3.start_time >= parent.start_time


def test_trace_start_time():
    """Test that trace_start_time returns the root run's
    start time for all nested runs."""
    mock_client = MagicMock(spec=Client)

    # Create a nested hierarchy: root -> child1 -> grandchild
    #                                 -> child2
    root = RunTree(name="root", client=mock_client)
    child1 = root.create_child(name="child1")
    grandchild = child1.create_child(name="grandchild")
    child2 = root.create_child(name="child2")

    # All runs should have the same trace_start_time as the root's start_time
    assert root.trace_start_time == root.start_time
    assert child1.trace_start_time == root.start_time
    assert grandchild.trace_start_time == root.start_time
    assert child2.trace_start_time == root.start_time

    # Verify trace_start_time is timezone-aware (UTC)
    assert root.trace_start_time.tzinfo == timezone.utc
    assert child1.trace_start_time.tzinfo == timezone.utc


def test_to_headers_does_not_serialize_replicas():
    mock_client = MagicMock(spec=Client)
    rt = RunTree(
        name="test",
        run_type="chain",
        client=mock_client,
        replicas=[
            {
                "api_key": "secret-key",
                "api_url": "https://attacker.com",
                "project_name": "safe-project",
                "updates": {"reroot": True},
            }
        ],
    )
    headers = rt.to_headers()
    baggage = headers.get("baggage", "")

    assert "replicas" not in baggage
    assert "secret-key" not in baggage
    assert "attacker.com" not in baggage
    assert "safe-project" not in baggage


def test_from_headers_filters_replica_credentials():
    replicas_json = json.dumps(
        [
            {
                "api_key": "injected-key",
                "api_url": "https://evil.com/exfil",
                "project_name": "legit-project",
                "updates": {"reroot": True},
            }
        ]
    )
    baggage = f"langsmith-replicas={urllib.parse.quote(replicas_json)}"
    headers = {
        "langsmith-trace": "20240101T000000000000Z00000000-0000-0000-0000-000000000001",
        "baggage": baggage,
    }

    parsed = RunTree.from_headers(headers)

    assert parsed is not None
    assert parsed.replicas is not None
    assert len(parsed.replicas) == 1
    replica = parsed.replicas[0]
    assert "api_key" not in replica
    assert "api_url" not in replica
    assert replica.get("project_name") == "legit-project"
    assert replica.get("updates") == {"reroot": True}


class TestNonRecordingRunTree:
    """Tests for the NonRecordingRunTree class."""

    def test_is_recording_returns_false(self):
        """Test that is_recording returns False for NonRecordingRunTree."""
        run = NonRecordingRunTree()
        assert run.is_recording() is False

    def test_run_tree_is_recording_returns_true(self):
        """Test that is_recording returns True for regular RunTree."""
        mock_client = MagicMock(spec=Client)
        run = RunTree(name="test", client=mock_client)
        assert run.is_recording() is True

    def test_properties_return_placeholders(self):
        """Test that properties return appropriate placeholder values."""
        run = NonRecordingRunTree()
        assert run.id == UUID("00000000-0000-0000-0000-000000000000")
        assert run.trace_id == UUID("00000000-0000-0000-0000-000000000000")
        assert run.dotted_order == ""
        assert run.name == ""
        assert run.run_type == "chain"
        assert run.session_name == ""

    def test_methods_are_noops(self):
        """Test that all methods execute without error and do nothing."""
        run = NonRecordingRunTree()

        # These should all execute without error
        run.set(inputs={"a": 1}, outputs={"b": 2})
        run.add_tags(["tag1", "tag2"])
        run.add_metadata({"key": "value"})
        run.add_outputs({"output": "data"})
        run.add_inputs({"input": "data"})
        run.add_event({"name": "event"})
        run.end(outputs={"final": "output"})
        run.post()
        run.patch()
        run.wait()

        # get_url should return empty string
        assert run.get_url() == ""

    def test_create_child_returns_self(self):
        """Test that create_child returns the same instance (no nesting)."""
        run = NonRecordingRunTree()
        child = run.create_child("child_name")
        assert child is run

        # Nested calls should all return the same instance
        grandchild = child.create_child("grandchild")
        assert grandchild is run

    def test_metadata_dict_is_mutable_but_noop(self):
        """Test that metadata can be accessed and mutated without error."""
        run = NonRecordingRunTree()

        # Should be able to access and mutate metadata
        run.metadata["key"] = "value"
        assert run.metadata.get("key") == "value"

        # But add_metadata is a no-op (doesn't actually add to the dict)
        run.add_metadata({"other": "data"})
        # The no-op doesn't add to metadata
        assert "other" not in run.metadata

    def test_outputs_setter_is_noop(self):
        """Test that setting outputs is a no-op."""
        run = NonRecordingRunTree()
        run.outputs = {"should": "be ignored"}
        # Setter is a no-op, so outputs dict should be empty
        assert run.outputs == {}

    def test_repr(self):
        """Test string representation."""
        run = NonRecordingRunTree()
        assert repr(run) == "NonRecordingRunTree()"

    def test_interface_matches_run_tree(self):
        """Test that NonRecordingRunTree has the same public interface as RunTree.

        This ensures that code using get_current_run_tree() can call any method
        without checking is_recording() first.

        The test dynamically introspects RunTree to find all public methods,
        so if a new method is added to RunTree, this test will automatically
        fail if NonRecordingRunTree doesn't implement it.
        """
        # Methods that users call on a run tree instance
        # These are dynamically discovered from RunTree class, minus exclusions
        excluded_from_interface = {
            # Pydantic internals
            "model_copy",
            "model_dump",
            "model_dump_json",
            "model_post_init",
            "model_validate",
            "model_validate_json",
            "model_validate_strings",
            "model_construct",
            "model_json_schema",
            "model_parametrized_name",
            "model_rebuild",
            "model_computed_fields",
            "model_config",
            "model_extra",
            "model_fields",
            "model_fields_set",
            "copy",
            "dict",
            "json",
            "parse_obj",
            "parse_raw",
            "parse_file",
            "schema",
            "schema_json",
            "validate",
            "update_forward_refs",
            "from_orm",
            "construct",
            # RunTree-specific methods not needed on NonRecordingRunTree
            "from_dotted_order",
            "from_headers",
            "from_runnable_config",
            "to_headers",
            "infer_defaults",
            "ensure_dotted_order",
            # RunTree-specific properties not part of the shared interface
            "client",
            "ls_client",
            "parent_run",
            "parent_run_id",
            "parent_dotted_order",
            "child_runs",
            "session_id",
            "reference_example_id",
            "start_time",
            "end_time",
            "error",
            "serialized",
            "attachments",
            "dangerously_allow_filesystem",
            "replicas",
            "trace_start_time",
            # Properties from base schema not needed on NonRecordingRunTree
            "latency",
            "revision_id",
        }

        # Get public methods and properties defined on RunTree class
        # (not inherited from object, not dunder, not excluded)
        run_tree_interface: set[str] = set()
        for name in dir(RunTree):
            if name.startswith("_"):
                continue
            if name in excluded_from_interface:
                continue
            # Check if it's defined on RunTree (not just inherited from object)
            if hasattr(object, name):
                continue
            run_tree_interface.add(name)

        # Also include key properties that users access on run trees
        # (Pydantic fields are only on instances, not in dir(Class))
        required_properties = {
            "id",
            "trace_id",
            "dotted_order",
            "name",
            "run_type",
            "session_name",
            "tags",
            "inputs",
            "outputs",
            "events",
            "extra",
        }
        run_tree_interface.update(required_properties)

        # Check that NonRecordingRunTree has all the required interface members
        non_recording = NonRecordingRunTree()
        missing = []
        for name in run_tree_interface:
            if not hasattr(non_recording, name):
                missing.append(name)

        assert not missing, (
            f"NonRecordingRunTree missing from RunTree interface: {sorted(missing)}"
        )

        # For methods, check that signatures are compatible
        recording = RunTree(name="test", client=MagicMock(spec=Client))

        for name in run_tree_interface:
            # Skip properties (Pydantic fields only exist on instances)
            if name in required_properties:
                continue

            rec_attr = getattr(RunTree, name, None)
            if rec_attr is None:
                continue

            # Check if it's a method (function defined on class)
            if callable(rec_attr) and not isinstance(rec_attr, property):
                non_rec_method = getattr(non_recording, name)
                rec_method = getattr(recording, name)

                if not callable(non_rec_method):
                    continue  # Skip if it's become a property on instance

                try:
                    non_rec_sig = inspect.signature(non_rec_method)
                    rec_sig = inspect.signature(rec_method)

                    non_rec_params = set(non_rec_sig.parameters.keys())
                    rec_params = set(rec_sig.parameters.keys())

                    missing_params = rec_params - non_rec_params
                    assert not missing_params, (
                        f"NonRecordingRunTree.{name} missing params: {missing_params}"
                    )
                except (ValueError, TypeError):
                    # Some methods may not have inspectable signatures
                    pass
