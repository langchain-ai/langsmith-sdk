"""Examples using the `evaluate` API to evaluate a target system on a dataset."""

import logging

logging.basicConfig(level=logging.INFO)

# ruff: noqa: E402
# mypy: ignore-errors
# Prerequisites for the following examples:
from typing import Sequence

from langsmith import Client
from langsmith.evaluation import evaluate, evaluate_existing
from langsmith.schemas import Example, Run

client = Client()

client.clone_public_dataset(
    "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
)
dataset_name = "Evaluate Examples"


# Example 1: Evalute your target system on a dataset


## Example (row)-level evaluator
def accuracy(run: Run, example: Example):
    """Row-level evaluator for accuracy."""
    pred = run.outputs["output"]
    expected = example.outputs["answer"]
    return {"score": expected.lower() == pred.lower()}


## Summary evaluators - define your custom aggregation logic
def precision(runs: Sequence[Run], examples: Sequence[Example]):
    """Batch-level evaluator for precision."""
    # TP / (TP + FP)
    predictions = [run.outputs["output"].lower() for run in runs]
    expected = [example.outputs["answer"].lower() for example in examples]
    # yes and no are the only possible answers
    tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
    fp = sum([p == "yes" and e == "no" for p, e in zip(predictions, expected)])
    return {"score": tp / (tp + fp)}


## The target system / thing you want to evaluate


def predict(inputs: dict) -> dict:
    """This can be any function or just an API call to your app."""
    return {"output": "Yes"}


results = evaluate(
    predict,
    data=dataset_name,
    evaluators=[accuracy],
    summary_evaluators=[precision],
)


# Example 3: evaluating over only a subset of the examples
experiment_name = results.experiment_name

examples = client.list_examples(dataset_name=dataset_name, limit=5)
results = evaluate(
    predict,
    data=examples,
    evaluators=[accuracy],
    summary_evaluators=[precision],
    experiment_prefix="My Experiment",
)

# Example 4: Streaming each prediction to more easily + eagerly debug.
results = evaluate(
    predict,
    data=dataset_name,
    evaluators=[accuracy],
    summary_evaluators=[precision],
    blocking=False,
)
for i, result in enumerate(results):
    pass


# Example 5: Add evaluation results to an existing set of runs (within an experiment)


def predicted_length(run: Run, example: Example):
    """Row-level evaluator for the length of the prediction."""
    return {"score": len(next(iter(run.outputs)))}


def recall(runs: Sequence[Run], examples: Sequence[Example]):
    """Batch-level evaluator for recall."""
    predictions = [run.outputs["output"].lower() for run in runs]
    expected = [example.outputs["answer"].lower() for example in examples]
    tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
    fn = sum([p == "no" and e == "yes" for p, e in zip(predictions, expected)])
    return {"score": tp / (tp + fn)}


evaluate_existing(
    experiment_name,
    data=dataset_name,
    evaluators=[predicted_length],
    summary_evaluators=[recall],
)


# Example 2: Using Off-the-shelf evaluators from LangChain

from langsmith.evaluation import LangChainStringEvaluator


def prepare_criteria_data(run: Run, example: Example):
    """Prepare the data for the criteria evaluator."""
    return {
        "prediction": run.outputs["output"],
        "reference": example.outputs["answer"],
        "input": str(example.inputs),
    }


results = evaluate(
    predict,
    data=dataset_name,
    evaluators=[
        accuracy,
        # Loads the evaluator from LangChain
        LangChainStringEvaluator("embedding_distance"),
        LangChainStringEvaluator(
            "labeled_criteria",
            config={
                "criteria": {
                    "usefulness": "The prediction is useful if it is correct"
                    " and/or asks a useful followup question."
                },
            },
        ).as_run_evaluator(prepare_data=prepare_criteria_data),
    ],
    summary_evaluators=[precision],
)

# Example 6: Evaluate a langchain object

from langchain_core.runnables import chain as as_runnable


@as_runnable
def nested_predict(inputs):
    """Object can be nested."""
    return {"output": "Yes"}


@as_runnable
def lc_predict(inputs):
    """LangChain runnable object."""
    return nested_predict.invoke(inputs)


results = evaluate(
    lc_predict.invoke,
    data=dataset_name,
    evaluators=[accuracy],
    summary_evaluators=[precision],
)


# TODO: Comparing against an EXISTING test run
# I think this should be a separate API honestly to remove ambiguity,
# since you may want to mix ground truth "correctness" metrics with
# other metrics that are not directly comparable to the ground truth.
# Maybe something like
# def preferred(target: Run, baseline: Run):
#     return {"score": target.outputs["output"] > baseline.outputs["output"]}
# evaluate_relative(predict, baseline=experiment_name/id/class,
# evaluators=[predicted_length])
# TODO: Evaluate against RAW PREDICTIONS
# If I have a set of predictions like {"output": "foo"}
# Evaluate COULD create a new experiment with those predictions and then
# call the evaluators.
# This could be useful if youw anted to just run inference separately
