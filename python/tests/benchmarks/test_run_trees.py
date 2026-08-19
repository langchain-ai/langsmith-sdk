"""Benchmarks for `RunTree`.

`RunTree` is the object every tracer builds: creating it derives UUIDv7 ids and
dotted orders, and `post()`/`patch()` serialize the run and hand it to the
client. All of this runs inline in user code, so it is pure overhead added to
the traced application.
"""

from langsmith.client import Client
from langsmith.run_trees import RunTree
from tests.benchmarks._payloads import (
    create_json_with_large_array,
    mock_session,
)


def _client() -> Client:
    return Client(session=mock_session(), api_key="fake", auto_batch_tracing=False)


def _create_run_trees(client: Client, n: int) -> None:
    for i in range(n):
        RunTree(name=str(i), client=client).post()


def test_create_run_trees(benchmark):
    client = _client()
    benchmark(_create_run_trees, client, 200)


def _build_tree(client: Client, depth: int, width: int) -> RunTree:
    root = RunTree(name="root", client=client, inputs={"question": "hello"})
    frontier = [root]
    for level in range(depth):
        next_frontier = []
        for parent in frontier:
            for i in range(width):
                child = parent.create_child(
                    name=f"child_{level}_{i}",
                    run_type="llm",
                    inputs={"prompt": "hello world"},
                )
                child.end(outputs={"generation": "hi there"})
                next_frontier.append(child)
        frontier = next_frontier
    return root


def test_build_nested_run_tree(benchmark):
    """Deriving dotted orders and metadata for a fan-out of child runs."""
    client = _client()
    benchmark(_build_tree, client, 3, 4)


def _post_tree(root: RunTree) -> None:
    root.post(exclude_child_runs=False)


def test_post_nested_run_tree(benchmark):
    client = _client()
    root = _build_tree(client, 2, 5)
    benchmark(_post_tree, root)


def _post_and_patch(client: Client, inputs: dict, outputs: dict) -> None:
    run = RunTree(name="run", client=client, inputs=inputs, run_type="chain")
    run.post()
    run.end(outputs=outputs)
    run.patch()


def test_post_and_patch_large_run(benchmark):
    """Full lifecycle of a single run carrying a realistic payload."""
    client = _client()
    inputs = create_json_with_large_array(200)
    outputs = create_json_with_large_array(200)
    benchmark(_post_and_patch, client, inputs, outputs)
