import asyncio
import datetime
import functools
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Callable, Iterator, Optional, Sequence, Tuple, TypeVar

import pytest

from langsmith import Client, aevaluate, evaluate, expect, test
from langsmith import utils as ls_utils
from langsmith.evaluation import EvaluationResult, EvaluationResults
from langsmith.schemas import Example, Run

T = TypeVar("T")

logger = logging.getLogger(__name__)

_VERSION_TAG = "test_version"

# Answers for the seeded dataset. A yes/no mix keeps the `precision` summary
# evaluator meaningful: it divides by the number of yes/no answers.
_SEEDED_ANSWERS = ["Yes", "No", "Yes", "Yes", "No", "Yes", "No", "Yes", "Yes", "No"]
_NUM_EXAMPLES = len(_SEEDED_ANSWERS)


@contextmanager
def suppress_warnings():
    logger = logging.getLogger()
    current_level = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logger.setLevel(current_level)


def wait_for(
    condition: Callable[[], Tuple[T, bool]],
    max_sleep_time: int = 120,
    sleep_time: int = 3,
) -> T:
    """Wait for a condition to be true."""
    start_time = time.time()
    last_e = None
    while (time.time() - start_time) < max_sleep_time:
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


def _tag_seeded_version(client: Client, dataset_id: uuid.UUID) -> Optional[str]:
    """Tag the dataset's current version, if this deployment records versions.

    Returns the tag to pass as `as_of`, or None when no version shows up — some
    deployments don't serve `/datasets/{id}/version` for a freshly seeded
    dataset, and pinning a version isn't what these tests are about.
    """
    deadline = time.time() + 30
    while True:
        for kwargs in (
            {"tag": "latest"},
            {"as_of": datetime.datetime.now(datetime.timezone.utc)},
        ):
            try:
                version = client.read_dataset_version(dataset_id=dataset_id, **kwargs)
                # `update_dataset_tag` needs an exact version, not just any timestamp.
                client.update_dataset_tag(
                    dataset_id=dataset_id, as_of=version.as_of, tag=_VERSION_TAG
                )
                return _VERSION_TAG
            except ls_utils.LangSmithNotFoundError:
                continue
        if time.time() >= deadline:
            logger.warning(
                "No dataset version available after 30s; reading examples untagged."
            )
            return None
        time.sleep(2)


@pytest.fixture(scope="module")
def evaluate_examples() -> Iterator[Tuple[str, Optional[str]]]:
    """Seed a dataset and yield `(dataset_name, as_of)`.

    These tests used to clone a public dataset from the prod app and read the
    `test_version` tag off it. That tag only exists on the prod copy, so on any
    other deployment `list_examples(as_of="test_version")` came back empty.
    """
    client = Client()
    dataset_name = f"Evaluate Examples - {uuid.uuid4().hex[:12]}"
    dataset = client.create_dataset(dataset_name=dataset_name)
    try:
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {
                    "inputs": {
                        "context": f"Context {i}",
                        "question": f"Is this question {i}?",
                    },
                    "outputs": {"answer": answer},
                }
                for i, answer in enumerate(_SEEDED_ANSWERS)
            ],
        )
        yield dataset_name, _tag_seeded_version(client, dataset.id)
    finally:
        client.delete_dataset(dataset_id=dataset.id)


async def test_error_handling_evaluators(evaluate_examples: Tuple[str, Optional[str]]):
    client = Client()
    dataset_name, as_of = evaluate_examples

    # Case 1: Normal dictionary return
    def error_dict_evaluator(run: Run, example: Example):
        if True:  # This condition ensures the error is always raised
            raise ValueError("Error in dict evaluator")
        return {"key": "dict_key", "score": 1}

    # Case 2: EvaluationResult return
    def error_evaluation_result(run: Run, example: Example):
        if True:  # This condition ensures the error is always raised
            raise ValueError("Error in EvaluationResult evaluator")
        return EvaluationResult(key="eval_result_key", score=1)

    # Case 3: EvaluationResults return
    def error_evaluation_results(run: Run, example: Example):
        if True:  # This condition ensures the error is always raised
            raise ValueError("Error in EvaluationResults evaluator")
        return EvaluationResults(
            results=[
                EvaluationResult(key="eval_results_key1", score=1),
                EvaluationResult(key="eval_results_key2", score=2),
            ]
        )

    # Case 4: Dictionary without 'key' field
    def error_dict_no_key(run: Run, example: Example):
        if True:  # This condition ensures the error is always raised
            raise ValueError("Error in dict without key evaluator")
        return {"score": 1}

    # Case 5: dict-style results
    def error_evaluation_results_dict(run: Run, example: Example):
        if True:  # This condition ensures the error is always raised
            raise ValueError("Error in EvaluationResults dict evaluator")

        return {
            "results": [
                dict(key="eval_results_dict_key1", score=1),
                {"key": "eval_results_dict_key2", "score": 2},
                EvaluationResult(key="eval_results_dict_key3", score=3),
            ]
        }

    def predict(inputs: dict) -> dict:
        return {"output": "Yes"}

    with suppress_warnings():
        sync_results = evaluate(
            predict,
            data=client.list_examples(
                dataset_name=dataset_name,
                as_of=as_of,
            ),
            evaluators=[
                error_dict_evaluator,
                error_evaluation_result,
                error_evaluation_results,
                error_dict_no_key,
                error_evaluation_results_dict,
            ],
            max_concurrency=1,  # To ensure deterministic order
        )

    assert len(sync_results) == _NUM_EXAMPLES

    def check_results(results):
        for result in results:
            eval_results = result["evaluation_results"]["results"]
            assert len(eval_results) == 8

            # Check error handling for each evaluator
            assert eval_results[0].key == "dict_key"
            assert "Error in dict evaluator" in eval_results[0].comment
            assert eval_results[0].extra.get("error") is True

            assert eval_results[1].key == "eval_result_key"
            assert "Error in EvaluationResult evaluator" in eval_results[1].comment
            assert eval_results[1].extra.get("error") is True

            assert eval_results[2].key == "eval_results_key1"
            assert "Error in EvaluationResults evaluator" in eval_results[2].comment
            assert eval_results[2].extra.get("error") is True

            assert eval_results[3].key == "eval_results_key2"
            assert "Error in EvaluationResults evaluator" in eval_results[3].comment
            assert eval_results[3].extra.get("error") is True

            assert eval_results[4].key == "error_dict_no_key"
            assert "Error in dict without key evaluator" in eval_results[4].comment
            assert eval_results[4].extra.get("error") is True

            assert eval_results[5].key == "eval_results_dict_key1"
            assert (
                "Error in EvaluationResults dict evaluator" in eval_results[5].comment
            )
            assert eval_results[5].extra.get("error") is True

            assert eval_results[6].key == "eval_results_dict_key2"
            assert (
                "Error in EvaluationResults dict evaluator" in eval_results[6].comment
            )
            assert eval_results[6].extra.get("error") is True

            assert eval_results[7].key == "eval_results_dict_key3"
            assert (
                "Error in EvaluationResults dict evaluator" in eval_results[7].comment
            )
            assert eval_results[7].extra.get("error") is True

    check_results(sync_results)

    async def apredict(inputs: dict):
        return predict(inputs)

    with suppress_warnings():
        async_results = await aevaluate(
            apredict,
            data=list(
                client.list_examples(
                    dataset_name=dataset_name,
                    as_of=as_of,
                )
            ),
            evaluators=[
                error_dict_evaluator,
                error_evaluation_result,
                error_evaluation_results,
                error_dict_no_key,
                error_evaluation_results_dict,
            ],
            max_concurrency=1,  # To ensure deterministic order
        )

    assert len(async_results) == _NUM_EXAMPLES
    check_results([res async for res in async_results])


@functools.lru_cache(maxsize=1)
def _has_pandas() -> bool:
    try:
        import pandas  # noqa

        return True

    except Exception:
        return False


async def test_aevaluate():
    client = Client()
    dataset = client.clone_public_dataset(
        "https://smith.langchain.com/public/2bbf4a10-c3d5-4868-9e96-400df97fed69/d"
    )

    def accuracy(run: Run, example: Example):
        pred = run.outputs["output"]  # type: ignore
        expected = example.outputs["answer"]  # type: ignore
        return {"score": expected.lower() == pred.lower()}

    async def slow_accuracy(run: Run, example: Example):
        pred = run.outputs["output"]  # type: ignore
        expected = example.outputs["answer"]  # type: ignore
        await asyncio.sleep(2)
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

    results = await aevaluate(
        apredict,
        data=dataset.name,
        evaluators=[accuracy, slow_accuracy],
        summary_evaluators=[precision],
        experiment_prefix="My Experiment",
        description="My Experiment Description",
        metadata={"my-prompt-version": "abcd-1234", "function": "aevaluate"},
    )
    assert len(results) == 10
    if _has_pandas():
        df = results.to_pandas()
        assert len(df) == 10
    async for _ in results:
        pass

    # Run it again with the existing project
    results2 = await aevaluate(
        apredict,
        data=dataset.name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=results.experiment_name,
    )
    assert len(results2) == 10

    # ... and again with the object
    experiment = client.read_project(project_name=results.experiment_name)
    results3 = await aevaluate(
        apredict,
        data=dataset.name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=experiment,
    )
    assert len(results3) == 10

    # ... and again with the ID
    results4 = await aevaluate(
        apredict,
        data=dataset.name,
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=str(experiment.id),
    )
    assert len(results4) == 10


def test_evaluate(evaluate_examples: Tuple[str, Optional[str]]):
    client = Client()
    dataset_name, as_of = evaluate_examples

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
        data=client.list_examples(dataset_name=dataset_name, as_of=as_of),
        evaluators=[accuracy],
        summary_evaluators=[precision],
        description="My sync experiment",
        metadata={
            "my-prompt-version": "abcd-1234",
            "function": "evaluate",
        },
        num_repetitions=3,
    )
    assert len(results) == 3 * _NUM_EXAMPLES
    if _has_pandas():
        df = results.to_pandas()
        assert len(df) == 3 * _NUM_EXAMPLES
        assert set(df.columns) == {
            "inputs.context",
            "inputs.question",
            "outputs.output",
            "error",
            "reference.answer",
            "feedback.accuracy",
            "execution_time",
            "example_id",
            "id",
        }
    examples = client.list_examples(dataset_name=dataset_name, as_of=as_of)
    for example in examples:
        assert len([r for r in results if r["example"].id == example.id]) == 3

    # Run it again with the existing project
    results2 = evaluate(
        predict,
        data=client.list_examples(dataset_name=dataset_name, as_of=as_of),
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=results.experiment_name,
    )
    assert len(results2) == _NUM_EXAMPLES

    # ... and again with the object
    experiment = client.read_project(project_name=results.experiment_name)
    results3 = evaluate(
        predict,
        data=client.list_examples(dataset_name=dataset_name, as_of=as_of),
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=experiment,
    )
    assert len(results3) == _NUM_EXAMPLES

    # ... and again with the ID
    results4 = evaluate(
        predict,
        data=client.list_examples(dataset_name=dataset_name, as_of=as_of),
        evaluators=[accuracy],
        summary_evaluators=[precision],
        experiment=str(experiment.id),
    )
    assert len(results4) == _NUM_EXAMPLES


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


async def test_aevaluate_good_error():
    client = Client()
    ds_name = "__Empty Dataset Do Not Modify"
    if not client.has_dataset(dataset_name=ds_name):
        client.create_dataset(dataset_name=ds_name)

    async def predict(inputs: dict):
        return {}

    match_val = "No examples found in the dataset."
    with pytest.raises(ValueError, match=match_val):
        await aevaluate(
            predict,
            data=ds_name,
        )

    with pytest.raises(ValueError, match="Must specify 'data'"):
        await aevaluate(
            predict,
            data=[],
        )
    with pytest.raises(ValueError, match=match_val):
        await aevaluate(
            predict,
            data=(_ for _ in range(0)),
        )


async def test_aevaluate_large_dataset_and_concurrency(
    evaluate_examples: Tuple[str, Optional[str]],
):
    client = Client()
    dataset_name, as_of = evaluate_examples

    async def mock_chat_completion(*, messages):
        await asyncio.sleep(1)
        return {
            "role": "assistant",
            "content": "Still thinking...",
        }

    def simulate_conversation_turn(*, existing, model_response):
        return existing + [
            model_response,
            {"role": "human", "content": "Think harder!"},
        ]

    # Will be traced by default
    async def target(inputs: dict) -> dict:
        messages = [
            {
                "role": "system",
                "content": "Come up with a math equation that solves the puzzle.",
            },
            # This dataset has inputs as a dict with a "statement" key
            {"role": "user", "content": "foo"},
        ]
        res = await mock_chat_completion(model="gpt-4o-mini", messages=messages)
        messages = simulate_conversation_turn(existing=messages, model_response=res)

        return {"equation": res}

    async def mock_evaluator_chat_completion(*, model, messages):
        await asyncio.sleep(2)
        return {
            "role": "assistant",
            "content": str(0.5),
        }

    async def mock_correctness_evaluator(outputs: dict, reference_outputs: dict):
        messages = [
            {"role": "system", "content": "Assign a score to the following output."},
            {
                "role": "user",
                "content": f"""
Actual: {outputs["equation"]}
""",
            },
        ]
        res = await mock_evaluator_chat_completion(model="o3-mini", messages=messages)
        return {
            "key": "correctness",
            "score": float(res["content"]),
            "comment": "The answer was a good attempt, but incorrect.",
        }

    client = Client()

    start = time.time()

    await client.aevaluate(
        target,
        data=client.list_examples(dataset_name=dataset_name, as_of=as_of),
        evaluators=[
            mock_correctness_evaluator,
        ],
        max_concurrency=3,
    )

    finish_time = time.time()
    assert (finish_time - start) <= 8.5
