import asyncio
import time
from typing import Callable, Sequence, Tuple, TypeVar

import pytest
from langchain_core.runnables import RunnableLambda

from langsmith import Client, aevaluate, evaluate, expect, test
from langsmith.schemas import Example, Run

T = TypeVar("T")


def wait_for(
    condition: Callable[[], Tuple[T, bool]],
    max_sleep_time: int = 120,
    sleep_time: int = 3,
) -> T:
    """Wait for a condition to be true."""
    start_time = time.time()
    last_e = None
    while time.time() - start_time < max_sleep_time:
        try:
            res, cond = condition()
            if cond:
                return res
        except Exception as e:
            last_e = e
            time.sleep(sleep_time)
    total_time = time.time() - start_time
    if last_e is not None:
        raise last_e
    raise ValueError(f"Callable did not return within {total_time}")


def test_evaluate():
    client = Client()
    _ = client.clone_public_dataset(
        "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
    )
    dataset_name = "Evaluate Examples"

    def accuracy(run: Run, example: Example):
        pred = run.outputs["output"]  # type: ignore
        expected = example.outputs["answer"]  # type: ignore
        return {"score": expected.lower() == pred.lower()}

    def precision(runs: Sequence[Run], examples: Sequence[Example]):
        predictions = [run.outputs["output"].lower() for run in runs]  # type: ignore
        expected = [example.outputs["answer"].lower() for example in examples]  # type: ignore
        tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        return {"score": tp / (tp + fp)}

    def predict(inputs: dict) -> dict:
        return {"output": "Yes"}

    results = evaluate(
        predict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        description="My sync experiment",
        metadata={
            "my-prompt-version": "abcd-1234",
            "function": "evaluate",
        },
        num_repetitions=3,
    )
    assert len(results) == 30
    examples = client.list_examples(dataset_name=dataset_name)
    for example in examples:
        assert len([r for r in results if r["example"].id == example.id]) == 3

    # Run it again with the existing project
    results2 = evaluate(
        predict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=results.experiment_name,
    )
    assert len(results2) == 10

    # ... and again with the object
    experiment = client.read_project(project_name=results.experiment_name)
    results3 = evaluate(
        predict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=experiment,
    )
    assert len(results3) == 10

    # ... and again with the ID
    results4 = evaluate(
        predict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=str(experiment.id),
    )
    assert len(results4) == 10


async def test_aevaluate():
    client = Client()
    _ = client.clone_public_dataset(
        "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
    )
    dataset_name = "Evaluate Examples"

    @RunnableLambda
    async def grand_child(x: str) -> str:
        return x

    @RunnableLambda
    async def child(x: str) -> str:
        return await grand_child.ainvoke(x)

    errors = []

    def accuracy(run: Run, example: Example):
        nonlocal errors
        try:
            assert run.child_runs
            assert run.child_runs[0].name == "child"
            assert run.child_runs[0].child_runs
            assert run.child_runs[0].child_runs[0].name == "grand_child"
        except Exception as e:
            errors.append(e)
            raise
        pred = run.outputs["output"]  # type: ignore
        expected = example.outputs["answer"]  # type: ignore
        return {"score": expected.lower() == pred.lower()}

    async def slow_accuracy(run: Run, example: Example):
        pred = run.outputs["output"]  # type: ignore
        expected = example.outputs["answer"]  # type: ignore
        await asyncio.sleep(5)
        return {"score": expected.lower() == pred.lower()}

    def precision(runs: Sequence[Run], examples: Sequence[Example]):
        predictions = [run.outputs["output"].lower() for run in runs]  # type: ignore
        expected = [example.outputs["answer"].lower() for example in examples]  # type: ignore
        tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
        fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
        return {"score": tp / (tp + fp)}

    async def apredict(inputs: dict) -> dict:
        await child.ainvoke(str(inputs))
        return {"output": "Yes"}

    results = await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[accuracy, slow_accuracy],
        summary_evaluators=[precision],
        experiment_prefix="My Experiment",
        description="My Experiment Description",
        metadata={
            "my-prompt-version": "abcd-1234",
            "function": "aevaluate",
        },
        num_repetitions=2,
    )
    assert len(results) == 20
    assert not errors
    examples = client.list_examples(dataset_name=dataset_name)
    all_results = [r async for r in results]
    all_examples = []
    for example in examples:
        count = 0
        for r in all_results:
            if r["run"].reference_example_id == example.id:
                count += 1
        assert count == 2
        all_examples.append(example)

    # Wait for there to be 2x runs vs. examples
    def check_run_count():
        current_runs = list(
            client.list_runs(project_name=results.experiment_name, is_root=True)
        )
        for r in current_runs:
            assert "accuracy" in r.feedback_stats
            assert "slow_accuracy" in r.feedback_stats
        return current_runs, len(current_runs) == 2 * len(all_examples)

    final_runs = wait_for(check_run_count, max_sleep_time=60, sleep_time=2)

    assert len(final_runs) == 2 * len(
        all_examples
    ), f"Expected {2 * len(all_examples)} runs, but got {len(final_runs)}"

    # Run it again with the existing project
    results2 = await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=results.experiment_name,
    )
    assert len(results2) == 10

    # ... and again with the object
    experiment = client.read_project(project_name=results.experiment_name)
    results3 = await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=experiment,
    )
    assert len(results3) == 10

    # ... and again with the ID
    results4 = await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=str(experiment.id),
    )
    assert len(results4) == 10


@test
def test_foo():
    expect(3 + 4).to_equal(7)


@pytest.fixture
def some_input():
    return "Some input"


@pytest.fixture
def expected_output():
    return "input"


@test(output_keys=["expected_output"])
def test_bar(some_input: str, expected_output: str):
    expect(some_input).to_contain(expected_output)


@test
async def test_baz():
    await asyncio.sleep(0.1)
    expect(3 + 4).to_equal(7)
    return 7


@test
@pytest.mark.parametrize("x, y", [(1, 2), (2, 3)])
def test_foo_parametrized(x, y):
    expect(x + y).to_be_greater_than(0)
    return x + y


@test(output_keys=["z"])
@pytest.mark.parametrize("x, y, z", [(1, 2, 3), (2, 3, 5)])
def test_bar_parametrized(x, y, z):
    expect(x + y).to_equal(z)
    return {"z": x + y}


@test(test_suite_name="tests.evaluation.test_evaluation::test_foo_async_parametrized")
@pytest.mark.parametrize("x, y", [(1, 2), (2, 3)])
async def test_foo_async_parametrized(x, y):
    await asyncio.sleep(0.1)
    expect(x + y).to_be_greater_than(0)
    return x + y


@test(output_keys=["z"])
@pytest.mark.parametrize("x, y, z", [(1, 2, 3), (2, 3, 5)])
async def test_bar_async_parametrized(x, y, z):
    await asyncio.sleep(0.1)
    expect(x + y).to_equal(z)
    return {"z": x + y}


@test
def test_pytest_skip():
    pytest.skip("Skip this test")


@test
async def test_async_pytest_skip():
    pytest.skip("Skip this test")
