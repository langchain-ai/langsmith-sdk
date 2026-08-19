"""Benchmarks for `RunTree` creation and posting.

`RunTree` is the object every tracing integration builds, so the cost of
instantiating it (Pydantic validation, dotted order computation, UUID v7
generation) and of posting it to the client is on the critical path of any
traced application.
"""

import pytest

from langsmith.run_trees import RunTree


@pytest.mark.benchmark
def test_create_run_trees(benchmark, client):
    def run() -> None:
        for i in range(500):
            RunTree(name=str(i), ls_client=client)

    benchmark(run)


@pytest.mark.benchmark
def test_create_and_post_run_trees(benchmark, client):
    def run() -> None:
        for i in range(200):
            RunTree(name=str(i), ls_client=client).post()

    benchmark(run)


@pytest.mark.benchmark
def test_create_nested_run_tree(benchmark, client):
    inputs = {"messages": [{"role": "user", "content": "what is the weather?"}]}
    outputs = {"choices": [{"message": {"role": "assistant", "content": "sunny"}}]}

    def run() -> None:
        parent = RunTree(
            name="chain",
            run_type="chain",
            inputs=inputs,
            ls_client=client,
            extra={"metadata": {"ls_model_name": "gpt-4o-mini"}},
        )
        for i in range(50):
            child = parent.create_child(
                name=f"llm_{i}", run_type="llm", inputs=inputs, tags=["bench"]
            )
            child.end(outputs=outputs)
        parent.end(outputs=outputs)

    benchmark(run)


@pytest.mark.benchmark
def test_run_tree_to_headers(benchmark, client):
    run_tree = RunTree(name="parent", ls_client=client)
    child = run_tree.create_child(name="child", run_type="llm")

    def run() -> None:
        for _ in range(500):
            child.to_headers()

    benchmark(run)
