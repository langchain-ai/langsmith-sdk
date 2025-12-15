import datetime
from typing import Any
from unittest.mock import MagicMock

from langsmith.client import Client
from langsmith.run_helpers import traceable
from langsmith.run_trees import RunTree


def _uuid_v7_ms(uuid_obj) -> int:
    """Extract milliseconds since epoch from a UUIDv7 using string layout.

    UUIDv7 stores Unix time in ms in the first 12 hex chars of the canonical
    string representation (48 msb bits).
    """
    s = str(uuid_obj).replace("-", "")
    return int(s[:12], 16)


def test_traceable_uses_uuidv7_and_start_time_matches_run_id() -> None:
    captured: dict[str, Any] = {}

    # Use a parent run to ensure a child RunTree is created even if tracing is disabled
    parent = RunTree(name="parent", run_type="chain", inputs={})

    @traceable(run_type="chain")
    def fn(x: int, *, run_tree: RunTree) -> int:  # type: ignore[misc]
        # capture run_tree from injected arg
        captured["run_tree"] = run_tree
        return x + 1

    # Execute traced function with explicit parent
    assert fn(1, langsmith_extra={"run_tree": parent}) == 2

    run_tree: RunTree = captured["run_tree"]
    # UUID version must be 7
    assert run_tree.id.version == 7
    # Extract ms from UUID and compare to start_time
    id_ms = _uuid_v7_ms(run_tree.id)
    # Match the same calculation path used by uuid7(id from start_time)
    start_ms = int(run_tree.start_time.timestamp() * 1_000_000_000) // 1_000_000
    assert id_ms == start_ms


def test_run_tree_default_uuidv7_and_start_time_match() -> None:
    # Default RunTree should have v7 id and matching start_time
    rt = RunTree(name="test", run_type="chain", inputs={})

    assert rt.id.version == 7
    id_ms = _uuid_v7_ms(rt.id)
    start_ms = int(rt.start_time.timestamp() * 1_000_000_000) // 1_000_000
    assert id_ms == start_ms


def test_run_tree_explicit_start_time_matches_id() -> None:
    fixed_start = datetime.datetime(
        2024, 6, 7, 8, 9, 10, 123000, tzinfo=datetime.timezone.utc
    )
    rt = RunTree(name="test", run_type="chain", inputs={}, start_time=fixed_start)

    assert rt.id.version == 7
    id_ms = _uuid_v7_ms(rt.id)
    start_ms = int(rt.start_time.timestamp() * 1_000_000_000) // 1_000_000
    assert id_ms == start_ms


def test_post_and_patch_include_run_type_and_start_time() -> None:
    client = MagicMock(spec=Client)
    fixed_start = datetime.datetime(
        2024, 6, 7, 8, 9, 10, 123000, tzinfo=datetime.timezone.utc
    )
    rt = RunTree(
        name="post-patch-test",
        run_type="llm",
        inputs={"x": 1},
        start_time=fixed_start,
    )
    # Inject our dummy client (use _client for backwards-compat field)
    rt._client = client  # type: ignore[assignment]

    # Post should include run_type and start_time
    rt.post()
    assert client.create_run.called
    _, create_kwargs = client.create_run.call_args
    assert create_kwargs["run_type"] == "llm"
    assert create_kwargs["start_time"] == fixed_start

    # Patch should include run_type and start_time
    rt.patch()
    assert client.update_run.called
    _, update_kwargs = client.update_run.call_args
    assert update_kwargs["run_type"] == "llm"
    assert update_kwargs["start_time"] == fixed_start
