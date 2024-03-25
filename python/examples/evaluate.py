# Prerequisites for the following examples:
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

client.clone_public_dataset(
    "https://smith.langchain.com/public/419dcab2-1d66-4b94-8901-0357ead390df/d"
)
dataset_name = "Evaluate Examples"


# Example 1: Evalute your target system on a dataset


## Example (row)-level evaluator
def accuracy(run, example):
    """Row-level evaluator for accuracy."""
    pred = run.outputs["output"]
    expected = example.outputs["answer"]
    return {"score": expected.lower() == pred.lower()}


## Aggregate "batch" evaluators
def precision(runs, examples):
    """Batch-level evaluator for precision.s"""
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
    batch_evaluators=[precision],
)

# Example 2: Using Off-the-shelf evaluators from LangChain

from langsmith.evaluation import LangChainStringEvaluator

results = evaluate(
    predict,
    data=dataset_name,
    evaluators=[
        accuracy,
        # Loads the evaluator from LangChain
        LangChainStringEvaluator("embedding_distance"),
        LangChainStringEvaluator(
            "criteria",
            config={
                "criteria": {
                    "usefulness": "The prediction is useful if it is correct"
                    " and/or asks a useful followup question."
                },
            },
        ),
    ],
    batch_evaluators=[precision],
)

# Example 3: evaluating over only a subset of the examples
import itertools
import uuid


examples = list(itertools.islice(client.list_examples(dataset_name=dataset_name), 5))
experiment_name = f"My Experiment - {uuid.uuid4().hex[:4]}"
results = evaluate(
    predict,
    data=examples,
    evaluators=[accuracy],
    batch_evaluators=[precision],
    experiment=experiment_name,
)


# Example 4: Adding evaluation results to an existing set of runs (within an experiment)
runs = client.list_runs(project_name=experiment_name, execution_order=1)


def predicted_length(run, example):
    return {"score": len(next(iter(run.outputs)))}


def recall(runs, examples):
    predictions = [run.outputs["output"].lower() for run in runs]
    expected = [example.outputs["answer"].lower() for example in examples]
    tp = sum([p == e for p, e in zip(predictions, expected) if p == "yes"])
    fn = sum([p == "no" and e == "yes" for p, e in zip(predictions, expected)])
    return {"score": tp / (tp + fn)}


evaluate(
    runs, data=dataset_name, evaluators=[predicted_length], batch_evaluators=[recall]
)


# Example 5: Streaming each prediction to more easily + eagerly debug.
results = evaluate(
    predict,
    data=dataset_name,
    evaluators=[accuracy],
    batch_evaluators=[precision],
    blocking=False,
)
for i, result in enumerate(results):
    pass


# TODO: Comparing against an EXISTING test run
# I think this should be a separate API honestly to remove ambiguity,
# since you may want to mix ground truth "correctness" metrics with
# other metrics that are not directly comparable to the ground truth.
# Maybe something like
# def preferred(target: Run, baseline: Run):
#     return {"score": target.outputs["output"] > baseline.outputs["output"]}
# evaluate_relative(predict, baseline=experiment_name/id/class, evaluators=[predicted_length])
