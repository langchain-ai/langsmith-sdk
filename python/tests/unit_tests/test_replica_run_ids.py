"""A replica's run ID must be a pure function of the run ID and the project name.

`uuid7_deterministic` builds a UUIDv7 as 6 timestamp bytes + 10 hash-derived bytes.
When the original ID is not itself a v7 there is no timestamp to copy, and the wall
clock was substituted -- making the function impure. `_remap_for_project` derives the
same ancestor ID from several runs (a two-run tree derives the root's ID five times),
so any impurity splits the replica's trace. See REPLICAS.md R15.
"""

import queue
import time
import uuid
import warnings
from unittest.mock import MagicMock

from langsmith import Client
from langsmith._internal._uuid import uuid7_deterministic
from langsmith.run_trees import TIMESTAMP_LENGTH, RunTree, WriteReplica

SECONDARY = "secondary-project"


def _client():
    client = Client(
        api_url="https://main.example.com",
        api_key="main-key",
        session=MagicMock(),
        auto_batch_tracing=False,
    )
    client.tracing_queue = queue.PriorityQueue(maxsize=100)
    client.compressed_traces = None
    return client


def test_non_v7_run_id_pairs_post_with_patch():
    """The bug: a v4 run ID gave the replica an orphaned post and an unmatched patch."""
    client = _client()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # non-v7 IDs emit a deprecation warning
        rt = RunTree(
            name="r",
            run_type="chain",
            id=uuid.uuid4(),
            inputs={"a": 1},
            ls_client=client,
            project_name="primary",
            replicas=[WriteReplica(project_name=SECONDARY)],
        )
        rt.post()
        time.sleep(0.01)
        rt.end(outputs={"b": 2})
        rt.patch()

    ids: dict[str, str] = {}
    while not client.tracing_queue.empty():
        op = client.tracing_queue.get_nowait().item
        ids.setdefault(op.operation, str(op.id))
    assert ids["post"] == ids["patch"], "replica received two IDs for one run"


def test_ancestor_id_derives_identically_from_parent_and_child():
    """`_remap_for_project` derives an ancestor's ID from the ancestor itself and
    again from every descendant. All of them must agree or the trace splits."""
    client = _client()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parent = RunTree(
            name="parent",
            run_type="chain",
            id=uuid.uuid4(),
            inputs={},
            ls_client=client,
            project_name="primary",
            replicas=[WriteReplica(project_name=SECONDARY)],
        )
        child = parent.create_child(name="child", run_type="chain", inputs={})

        parent_remap = parent._remap_for_project(SECONDARY, None, primary=None)
        # Different millisecond: a clock-derived timestamp would diverge here.
        time.sleep(0.01)
        child_remap = child._remap_for_project(SECONDARY, None, primary=None)

    written = str(parent_remap["id"])
    assert str(child_remap["trace_id"]) == written, "child's trace_id orphaned"
    assert str(child_remap["parent_run_id"]) == written, "child's parent orphaned"
    first_segment = child_remap["dotted_order"].split(".")[0]
    assert first_segment[-TIMESTAMP_LENGTH:] == written, "dotted_order orphaned"


def test_non_v7_original_yields_conforming_uuid7():
    derived = uuid7_deterministic(uuid.uuid4(), "proj")
    assert derived.version == 7
    assert derived.variant == uuid.RFC_4122


def test_derivation_still_varies_with_both_inputs():
    original = uuid.uuid4()
    base = uuid7_deterministic(original, "proj")
    assert uuid7_deterministic(original, "other") != base
    assert uuid7_deterministic(uuid.uuid4(), "proj") != base
