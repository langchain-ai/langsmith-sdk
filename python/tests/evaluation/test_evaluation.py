import asyncio
from typing import Sequence

import pytest

from langsmith import Client, aevaluate, evaluate, expect, unit
from langsmith.schemas import Example, Run


def test_evaluate():
    client = Client()
    client.clone_public_dataset(
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

    evaluate(
        predict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        metadata={
            "my-prompt-version": "abcd-1234",
            "function": "evaluate",
        },
    )


async def test_aevaluate():
    client = Client()
    client.clone_public_dataset(
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

    async def apredict(inputs: dict) -> dict:
        await asyncio.sleep(0.1)
        return {"output": "Yes"}

    await aevaluate(
        apredict,
        data=dataset_name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment_prefix="My Experiment",
        metadata={
            "my-prompt-version": "abcd-1234",
            "function": "agevaluate",
        },
    )


@unit
def test_foo():
    expect(3 + 4).to_equal(7)


@pytest.fixture
def some_input():
    return "Some input"


@pytest.fixture
def expected_output():
    return "input"


@unit(output_keys=["expected_output"])
def test_bar(some_input: str, expected_output: str):
    expect(some_input).to_contain(expected_output)
