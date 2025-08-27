"""Test the eval runner."""

import asyncio
import functools
import itertools
import json
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Tuple
from unittest import mock
from unittest.mock import MagicMock

import pytest
from langchain_core.runnables import chain as as_runnable

from langsmith import Client, aevaluate, evaluate
from langsmith import schemas as ls_schemas
from langsmith.evaluation._runner import _get_target_args
from langsmith.evaluation.evaluator import (
    _normalize_comparison_evaluator_func,
    _normalize_evaluator_func,
    _normalize_summary_evaluator,
)


class FakeRequest:
    def __init__(self, ds_id, ds_name, ds_examples, tenant_id):
        self.created_session = None
        self.runs = {}
        self.should_fail = False
        self.ds_id = ds_id
        self.ds_name = ds_name
        self.ds_examples = ds_examples
        self.tenant_id = tenant_id

    def request(self, verb: str, endpoint: str, *args, **kwargs):
        if verb == "GET":
            if endpoint == "http://localhost:1984/datasets":
                res = MagicMock()
                res.json.return_value = {
                    "id": self.ds_id,
                    "created_at": "2021-09-01T00:00:00Z",
                    "name": self.ds_name,
                }
                return res
            elif endpoint == "http://localhost:1984/examples":
                res = MagicMock()
                res.json.return_value = [
                    e.dict() if not isinstance(e, dict) else e for e in self.ds_examples
                ]
                return res
            elif endpoint == "http://localhost:1984/sessions":
                res = {}  # type: ignore
                if kwargs["params"]["name"] == self.created_session["name"]:  # type: ignore
                    res = self.created_session  # type: ignore
                response = MagicMock()
                response.json.return_value = res
                return response
            elif (
                endpoint
                == f"http://localhost:1984/sessions/{self.created_session['id']}"
            ):  # type: ignore
                res = self.created_session  # type: ignore
                response = MagicMock()
                response.json.return_value = res
                return response
            else:
                self.should_fail = True
                raise ValueError(f"Unknown endpoint: {endpoint}")
        elif verb == "POST":
            if endpoint == "http://localhost:1984/sessions":
                self.created_session = json.loads(kwargs["data"]) | {
                    "tenant_id": self.tenant_id
                }
                response = MagicMock()
                response.json.return_value = self.created_session
                return response
            elif endpoint == "http://localhost:1984/runs/batch":
                loaded_runs = json.loads(kwargs["data"])
                posted = loaded_runs.get("post", [])
                patched = loaded_runs.get("patch", [])
                for p in posted:
                    self.runs[p["id"]] = p
                for p in patched:
                    self.runs[p["id"]].update(p)
                response = MagicMock()
                return response
            elif endpoint == "http://localhost:1984/runs/query":
                res = MagicMock()
                res.json.return_value = {
                    "runs": [
                        r
                        for r in self.runs.values()
                        if r["trace_id"] == r["id"] and r.get("reference_example_id")
                    ]
                }
                return res
            elif endpoint == "http://localhost:1984/feedback":
                response = MagicMock()
                response.json.return_value = {}
                return response
            elif endpoint == "http://localhost:1984/datasets/comparative":
                response = MagicMock()
                self.created_comparative_experiment = json.loads(kwargs["data"]) | {
                    "tenant_id": self.tenant_id,
                    "modified_at": datetime.now(),
                }
                response.json.return_value = self.created_comparative_experiment
                return response

            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")
        elif verb == "PATCH":
            if (
                endpoint
                == f"http://localhost:1984/sessions/{self.created_session['id']}"
            ):  # type: ignore
                updates = json.loads(kwargs["data"])
                self.created_session.update({k: v for k, v in updates.items() if v})  # type: ignore
                response = MagicMock()
                response.json.return_value = self.created_session
                return response
            else:
                self.should_fail = True
                raise ValueError(f"Unknown endpoint: {endpoint}")
        else:
            self.should_fail = True
            raise ValueError(f"Unknown verb: {verb}, {endpoint}")


def _wait_until(condition: Callable, timeout: int = 8):
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return
        time.sleep(0.1)
    raise TimeoutError("Condition not met")


def _create_example(idx: int) -> Tuple[ls_schemas.Example, Dict[str, Any]]:
    _id = uuid.uuid4()
    _created_at = datetime.now(timezone.utc)
    return ls_schemas.Example(
        id=_id,
        inputs={"in": idx},
        outputs={"answer": idx + 1},
        dataset_id="00886375-eb2a-4038-9032-efff60309896",
        created_at=_created_at,
        metadata={"meta": idx},
    ), {
        "id": _id,
        "dataset_id": "00886375-eb2a-4038-9032-efff60309896",
        "created_at": _created_at,
        "inputs": {"in": idx},
        "outputs": {"answer": idx + 1},
        "metadata": {"meta": idx},
        "attachment_urls": None,
    }


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
@pytest.mark.parametrize("blocking", [False, True])
@pytest.mark.parametrize("as_runnable", [False, True])
@pytest.mark.parametrize("upload_results", [False, True])
def test_evaluate_results(
    blocking: bool, as_runnable: bool, upload_results: bool
) -> None:
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    SPLIT_SIZE = 3
    NUM_REPETITIONS = 4
    ds_example_responses = [_create_example(i) for i in range(10)]
    ds_examples = [e[0] for e in ds_example_responses]
    dev_split = random.sample(ds_examples, SPLIT_SIZE)
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(
        ds_id, ds_name, [e[1] for e in ds_example_responses], tenant_id
    )
    session.request = fake_request.request
    client = Client(
        api_url="http://localhost:1984",
        api_key="123",
        session=session,
        info=ls_schemas.LangSmithInfo(
            batch_ingest_config=ls_schemas.BatchIngestConfig(
                size_limit_bytes=None,  # Note this field is not used here
                size_limit=100,
                scale_up_nthreads_limit=16,
                scale_up_qsize_trigger=1000,
                scale_down_nempty_trigger=4,
            )
        ),
    )
    client._tenant_id = tenant_id  # type: ignore

    ordering_of_stuff: List[str] = []
    locked = False

    lock = Lock()
    slow_index = None

    def predict(inputs: dict) -> dict:
        nonlocal locked
        nonlocal slow_index
        if len(ordering_of_stuff) > 2 and not locked:
            with lock:
                if len(ordering_of_stuff) > 2 and not locked:
                    locked = True
                    time.sleep(3)
                    slow_index = len(ordering_of_stuff)
                    ordering_of_stuff.append("predict")
                else:
                    ordering_of_stuff.append("predict")

        else:
            ordering_of_stuff.append("predict")
        return {"output": inputs["in"] + 1}

    if as_runnable:
        try:
            from langchain_core.runnables import RunnableLambda
        except ImportError:
            pytest.skip("langchain-core not installed.")
            return
        else:
            predict = RunnableLambda(predict)

    def score_value_first(run, example):
        ordering_of_stuff.append("evaluate")
        return {"score": 0.3}

    def score_unpacked_inputs_outputs(inputs, outputs):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    def score_unpacked_inputs_outputs_reference(inputs, outputs, reference_outputs):
        ordering_of_stuff.append("evaluate")
        return {"score": reference_outputs["answer"]}

    def score_unpacked_inputs_outputs_attachments(inputs, outputs, attachments):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    def score_unpacked_outputs(outputs):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    def eval_float(run, example):
        ordering_of_stuff.append("evaluate")
        return 0.2

    def eval_str(run, example):
        ordering_of_stuff.append("evaluate")
        return "good"

    def eval_list(run, example):
        ordering_of_stuff.append("evaluate")
        return [
            {"score": True, "key": "list_eval_bool"},
            {"score": 1, "key": "list_eval_int"},
        ]

    def summary_eval_runs_examples(runs_, examples_):
        return {"score": len(runs_[0].dotted_order)}

    def summary_eval_inputs_outputs(inputs, outputs):
        return [{"score": len([x["in"] for x in inputs])}]

    def summary_eval_outputs_reference(outputs, reference_outputs):
        return len([x["answer"] for x in reference_outputs])

    evaluators = [
        score_value_first,
        score_unpacked_inputs_outputs,
        score_unpacked_inputs_outputs_reference,
        score_unpacked_inputs_outputs_attachments,
        score_unpacked_outputs,
        eval_float,
        eval_str,
        eval_list,
    ]

    summary_evaluators = [
        summary_eval_runs_examples,
        summary_eval_inputs_outputs,
        summary_eval_outputs_reference,
    ]

    results = evaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=evaluators,
        summary_evaluators=summary_evaluators,
        num_repetitions=NUM_REPETITIONS,
        blocking=blocking,
        upload_results=upload_results,
        max_concurrency=None,
    )
    if not blocking:
        deltas = []
        last = None
        start = time.time()
        now = start
        for _ in results:
            now = time.time()
            deltas.append((now - last) if last is not None else 0)  # type: ignore
            last = now
        assert now - start > 1.5
        # Essentially we want to check that 1 delay is > 1.5s and the rest are < 0.1s
        assert len(deltas) == SPLIT_SIZE * NUM_REPETITIONS
        assert slow_index is not None

        total_quick = sum([d < 0.5 for d in deltas])
        total_slow = sum([d > 0.5 for d in deltas])
        tolerance = 3
        assert total_slow < tolerance
        assert total_quick > (SPLIT_SIZE * NUM_REPETITIONS - 1) - tolerance

    for r in results:
        assert r["run"].outputs["output"] == r["example"].inputs["in"] + 1  # type: ignore
        assert set(r["run"].outputs.keys()) == {"output"}  # type: ignore
        assert len(r["evaluation_results"]["results"]) == len(evaluators) + 1
        assert all(
            er.score is not None or er.value is not None
            for er in r["evaluation_results"]["results"]
        )
    assert len(results._summary_results["results"]) == len(summary_evaluators)

    N_PREDS = SPLIT_SIZE * NUM_REPETITIONS
    if upload_results:
        assert fake_request.created_session
        _wait_until(lambda: fake_request.runs)
        _wait_until(lambda: len(ordering_of_stuff) == (N_PREDS * (len(evaluators) + 1)))
        _wait_until(lambda: slow_index is not None)
        # Want it to be interleaved
        assert ordering_of_stuff[:N_PREDS] != ["predict"] * N_PREDS
    else:
        assert not fake_request.created_session

    # It's delayed, so it'll be the penultimate event
    # Will run all other preds and evals, then this, then the last eval
    assert slow_index == (len(evaluators) + 1) * (N_PREDS - 1)

    if upload_results:

        def score_value(run, example):
            return {"score": 0.7}

        ex_results = evaluate(
            fake_request.created_session["name"],
            evaluators=[score_value],
            client=client,
            blocking=blocking,
        )
        second_item = next(itertools.islice(iter(ex_results), 1, 2))
        first_list = list(ex_results)
        second_list = list(ex_results)
        second_item_after = next(itertools.islice(iter(ex_results), 1, 2))
        assert len(first_list) == len(second_list) == SPLIT_SIZE * NUM_REPETITIONS
        assert first_list == second_list
        assert second_item == second_item_after
        dev_xample_ids = [e.id for e in dev_split]
        for r in ex_results:
            assert r["example"].id in dev_xample_ids
            assert r["evaluation_results"]["results"][0].score == 0.7
            assert r["run"].reference_example_id in dev_xample_ids
        assert not fake_request.should_fail
        ex_results2 = evaluate(
            fake_request.created_session["name"],
            evaluators=[score_value],
            client=client,
            blocking=blocking,
        )
        assert [x["evaluation_results"]["results"][0].score for x in ex_results2] == [
            x["evaluation_results"]["results"][0].score for x in ex_results
        ]

    # Returning list of non-dicts not supported.
    def bad_eval_list(run, example):
        ordering_of_stuff.append("evaluate")
        return ["foo", 1]

    results = evaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=[bad_eval_list],
        num_repetitions=NUM_REPETITIONS,
        blocking=blocking,
    )
    for r in results:
        assert r["evaluation_results"]["results"][0].extra == {"error": True}

    # test invalid evaluators
    def eval1(bar, *, inputs, outputs):
        pass

    # if more than 2 positional args, they must all have default arg names
    # (run, example, ...)
    def eval2(x, y, inputs):
        pass

    evaluators = [eval1, eval2]

    for eval_ in evaluators:
        with pytest.raises(ValueError, match="Invalid evaluator function."):
            _normalize_evaluator_func(eval_)

        with pytest.raises(ValueError, match="Invalid evaluator function."):
            evaluate(
                (lambda inputs: inputs),
                data=ds_examples,
                evaluators=[eval_],
                client=client,
            )

    def predict_with_meta(inputs: dict, metadata: dict) -> dict:
        return metadata

    results = client.evaluate(predict_with_meta, data=ds_examples[:1])
    for r, ex in zip(results, ds_examples):
        assert r["run"].outputs == ex.metadata


def test_evaluate_raises_for_async():
    async def my_func(inputs: dict):
        pass

    match = "Async functions are not supported by"
    with pytest.raises(ValueError, match=match):
        evaluate(my_func, data="foo")

    async def my_other_func(inputs: dict, other_val: int):
        pass

    with pytest.raises(ValueError, match=match):
        evaluate(functools.partial(my_other_func, other_val=3), data="foo")

    if sys.version_info < (3, 10):
        return
    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError:
        pytest.skip("langchain-core not installed.")
        return
    with pytest.raises(ValueError, match=match):
        evaluate(
            functools.partial(RunnableLambda(my_func).ainvoke, inputs={"foo": "bar"}),
            data="foo",
        )


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
@pytest.mark.parametrize("blocking", [False, True])
@pytest.mark.parametrize("as_runnable", [False, True])
@pytest.mark.parametrize("upload_results", [False, True])
async def test_aevaluate_results(
    blocking: bool, as_runnable: bool, upload_results: bool
) -> None:
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    SPLIT_SIZE = 3
    NUM_REPETITIONS = 4
    ds_example_responses = [_create_example(i) for i in range(10)]
    ds_examples = [e[0] for e in ds_example_responses]
    dev_split = random.sample(ds_examples, SPLIT_SIZE)
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(
        ds_id, ds_name, [e[1] for e in ds_example_responses], tenant_id
    )
    session.request = fake_request.request
    client = Client(
        api_url="http://localhost:1984",
        api_key="123",
        session=session,
        info=ls_schemas.LangSmithInfo(
            batch_ingest_config=ls_schemas.BatchIngestConfig(
                size_limit_bytes=None,  # Note this field is not used here
                size_limit=100,
                scale_up_nthreads_limit=16,
                scale_up_qsize_trigger=1000,
                scale_down_nempty_trigger=4,
            )
        ),
    )
    client._tenant_id = tenant_id  # type: ignore

    ordering_of_stuff: List[str] = []
    locked = False

    lock = asyncio.Lock()
    slow_index = None

    async def predict(inputs: dict) -> dict:
        nonlocal locked
        nonlocal slow_index

        if len(ordering_of_stuff) > 2 and not locked:
            async with lock:
                if len(ordering_of_stuff) > 2 and not locked:
                    locked = True
                    await asyncio.sleep(3)
                    slow_index = len(ordering_of_stuff)
                    ordering_of_stuff.append("predict")
                else:
                    ordering_of_stuff.append("predict")

        else:
            ordering_of_stuff.append("predict")
        return {"output": inputs["in"] + 1}

    if as_runnable:
        try:
            from langchain_core.runnables import RunnableLambda
        except ImportError:
            pytest.skip("langchain-core not installed.")
            return
        else:
            predict = RunnableLambda(predict)

    async def score_value_first(run, example):
        ordering_of_stuff.append("evaluate")
        return {"score": 0.3}

    async def score_unpacked_inputs_outputs(inputs, outputs):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    async def score_unpacked_inputs_outputs_reference(
        inputs, outputs, reference_outputs
    ):
        ordering_of_stuff.append("evaluate")
        return {"score": reference_outputs["answer"]}

    async def score_unpacked_inputs_outputs_attachments(inputs, outputs, attachments):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    async def score_unpacked_outputs(outputs):
        ordering_of_stuff.append("evaluate")
        return {"score": outputs["output"]}

    async def eval_float(run, example):
        ordering_of_stuff.append("evaluate")
        return 0.2

    async def eval_str(run, example):
        ordering_of_stuff.append("evaluate")
        return "good"

    async def eval_list(run, example):
        ordering_of_stuff.append("evaluate")
        return [
            {"score": True, "key": "list_eval_bool"},
            {"score": 1, "key": "list_eval_int"},
        ]

    def summary_eval_runs_examples(runs_, examples_):
        return {"score": len(runs_[0].dotted_order)}

    def summary_eval_inputs_outputs(inputs, outputs):
        return {"score": len([x["in"] for x in inputs])}

    def summary_eval_outputs_reference(outputs, reference_outputs):
        return {"score": len([x["answer"] for x in reference_outputs])}

    evaluators = [
        score_value_first,
        score_unpacked_inputs_outputs,
        score_unpacked_inputs_outputs_reference,
        score_unpacked_inputs_outputs_attachments,
        score_unpacked_outputs,
        eval_float,
        eval_str,
        eval_list,
    ]

    summary_evaluators = [
        summary_eval_runs_examples,
        summary_eval_inputs_outputs,
        summary_eval_outputs_reference,
    ]

    results = await aevaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=evaluators,
        summary_evaluators=summary_evaluators,
        num_repetitions=NUM_REPETITIONS,
        blocking=blocking,
        upload_results=upload_results,
        max_concurrency=None,
    )
    if not blocking:
        deltas: list = []
        start = time.time()
        last = start
        now = None
        async for _ in results:
            now = time.time()
            deltas.append((now - last))
            last = now
        total = now - start  # type: ignore
        assert 3.3 > total > 1.5

        # Essentially we want to check that most calls were very fast.
        assert len(deltas) == SPLIT_SIZE * NUM_REPETITIONS

        total_quick = sum([d < 0.5 for d in deltas])
        total_slow = sum([d > 0.5 for d in deltas])
        tolerance = 3
        assert total_slow < tolerance
        assert total_quick > (SPLIT_SIZE * NUM_REPETITIONS - 1) - tolerance
        assert max(deltas) > (total / 3)

    async for r in results:
        assert r["run"].outputs["output"] == r["example"].inputs["in"] + 1  # type: ignore
        assert set(r["run"].outputs.keys()) == {"output"}  # type: ignore
        assert all(
            er.score is not None or er.value is not None
            for er in r["evaluation_results"]["results"]
        )
    assert len(results._summary_results["results"]) == len(summary_evaluators)

    N_PREDS = SPLIT_SIZE * NUM_REPETITIONS

    if upload_results:
        assert fake_request.created_session
        _wait_until(lambda: fake_request.runs)
        _wait_until(lambda: len(ordering_of_stuff) == N_PREDS * (len(evaluators) + 1))
        _wait_until(lambda: slow_index is not None)
        # Want it to be interleaved
        assert ordering_of_stuff[:N_PREDS] != ["predict"] * N_PREDS
        assert slow_index is not None
        # It's delayed, so it'll be the penultimate event
        # Will run all other preds and evals, then this, then the last eval
        assert slow_index == (N_PREDS - 1) * (len(evaluators) + 1)

        assert fake_request.created_session["name"]
    else:
        assert not fake_request.created_session

    async def score_value(run, example):
        return {"score": 0.7}

    if upload_results:
        ex_results = await aevaluate(
            fake_request.created_session["name"],
            evaluators=[score_value],
            client=client,
            blocking=blocking,
        )
        all_results = [r async for r in ex_results]
        assert len(all_results) == SPLIT_SIZE * NUM_REPETITIONS
        dev_xample_ids = [e.id for e in dev_split]
        async for r in ex_results:
            assert r["example"].id in dev_xample_ids
            assert r["evaluation_results"]["results"][0].score == 0.7
            assert r["run"].reference_example_id in dev_xample_ids
        assert not fake_request.should_fail
        ex_results2 = await aevaluate(
            fake_request.created_session["name"],
            evaluators=[score_value],
            client=client,
            blocking=blocking,
        )
        assert [
            x["evaluation_results"]["results"][0].score async for x in ex_results2
        ] == [x["evaluation_results"]["results"][0].score for x in all_results]

    # Returning list of non-dicts not supported.
    async def bad_eval_list(run, example):
        ordering_of_stuff.append("evaluate")
        return ["foo", 1]

    results = await aevaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=[bad_eval_list],
        num_repetitions=NUM_REPETITIONS,
        blocking=blocking,
        upload_results=upload_results,
    )
    async for r in results:
        assert r["evaluation_results"]["results"][0].extra == {"error": True}

    # test invalid evaluators
    async def eval1(bar, *, inputs, outputs):
        pass

    # if more than 2 positional args, they must all have default arg names
    # (run, example, ...)
    async def eval2(x, y, inputs):
        pass

    evaluators = [eval1, eval2]

    async def atarget(inputs):
        return inputs

    for eval_ in evaluators:
        with pytest.raises(ValueError, match="Invalid evaluator function."):
            _normalize_evaluator_func(eval_)

        with pytest.raises(ValueError, match="Invalid evaluator function."):
            await aevaluate(
                atarget,
                data=ds_examples,
                evaluators=[eval_],
                client=client,
                upload_results=upload_results,
                blocking=blocking,
            )


@as_runnable
def nested_predict(inputs):
    return {"output": "Yes"}


@as_runnable
def lc_predict(inputs):
    return nested_predict.invoke(inputs)


async def async_inputs(inputs):
    return None


async def async_inputs_attachments(inputs, attachments):
    return None


async def async_inputs_metadata(inputs, metadata):
    return None


async def async_inputs_attachments_metadata(inputs, attachments, metadata):
    return None


async def async_extra_args(inputs, attachments, foo="bar"):
    return None


@pytest.mark.parametrize(
    "target,expected",
    [
        # Valid cases
        (lambda inputs: None, ["inputs"]),
        (lambda inputs, attachments: None, ["inputs", "attachments"]),
        (lambda inputs, metadata: None, ["inputs", "metadata"]),
        (
            lambda metadata, inputs, attachments: None,
            ["metadata", "inputs", "attachments"],
        ),
        (async_inputs, ["inputs"]),
        (async_inputs_attachments, ["inputs", "attachments"]),
        (async_inputs_metadata, ["inputs", "metadata"]),
        (async_inputs_attachments_metadata, ["inputs", "attachments", "metadata"]),
        # Mixed positional and keyword
        (lambda inputs, *, optional=None: None, ["inputs"]),
        (lambda inputs, attachments, *, optional=None: None, ["inputs", "attachments"]),
        (lambda inputs, *, attachments=None: None, ["inputs"]),
        # Positional args with defaults
        (
            lambda inputs, metadata, attachments, foo="bar": None,
            ["inputs", "metadata", "attachments"],
        ),
        (async_extra_args, ["inputs", "attachments"]),
        # Invalid parameter names
        (
            lambda x, y: None,
            "When passing multiple positional arguments without default values",
        ),
        (
            # should be 'inputs' not 'input'
            lambda input, attachment: None,
            "When passing multiple positional arguments without default values",
        ),
        # Too many parameters
        (
            lambda inputs, attachments, extra, extra2: None,
            re.escape(
                "Target function must accept at most three arguments without "
                "default values: (inputs, attachments, metadata)."
            ),
        ),
        # No positional parameters
        (
            lambda *, foo="bar": None,
            re.escape(
                "Target function must accept at least one positional argument (inputs)"
            ),
        ),
        # Non-callable
        ("not_a_function", []),
        # Runnable
        (lc_predict.invoke, ["inputs"]),
    ],
)
def test__get_target_args(target, expected):
    """Test the _include_attachments function with various input cases."""
    if isinstance(expected, str):
        with pytest.raises(ValueError, match=expected):
            _get_target_args(target)
    else:
        result = _get_target_args(target)
        assert result == expected


def valid_single_supported(inputs, *, optional=None):
    return {"score": 1}


async def valid_single_supported_async(inputs, *, optional=None):
    return {"score": 1}


def valid_two_arbitrary(foo, bar, *, optional=None):
    return {"score": 1}


async def valid_two_arbitrary_async(foo, bar, *, optional=None):
    return {"score": 1}


def valid_multiple_supported(inputs, outputs, reference_outputs, *, optional=None):
    return {"score": 1}


async def valid_multiple_supported_async(
    inputs, outputs, reference_outputs, *, optional=None
):
    return {"score": 1}


def invalid_single_unsupported(foo, *, optional=None):
    return {"score": 1}


async def invalid_single_unsupported_async(foo, *, optional=None):
    return {"score": 1}


def invalid_three_args(inputs, outputs, foo, *, optional=None):
    return {"score": 1}


async def invalid_three_args_async(inputs, outputs, foo, *, optional=None):
    return {"score": 1}


def kwarg_valid_two_arbitrary(*, foo, bar, optional=None):
    return {"score": 1}


def valid_additional_kwargs(*, foo, bar, optional=None, **kwargs):
    return {"score": 1}


def kwarg_valid_multiple_supported(
    *, inputs, outputs, reference_outputs, optional=None
):
    return {"score": 1}


async def kwarg_valid_two_arbitrary_async(*, foo, bar, optional=None):
    return {"score": 1}


async def valid_additional_kwargs_async(*, foo, bar, optional=None, **kwargs):
    return {"score": 1}


async def kwarg_valid_multiple_supported_async(
    *, inputs, outputs, reference_outputs, optional=None
):
    return {"score": 1}


def kwarg_invalid_single_unsupported(*, foo, optional=None):
    return {"score": 1}


def kwarg_invalid_three_args(*, inputs, outputs, foo, optional=None):
    return {"score": 1}


async def kwarg_invalid_single_unsupported_async(*, foo, optional=None):
    return {"score": 1}


async def kwarg_invalid_three_args_async(*, inputs, outputs, foo, optional=None):
    return {"score": 1}


def valid_mixed_positional_and_keyword(foo, *, bar, optional=None):
    return {"score": 1}


def valid_mixed_positional_and_keyword_with_reference_outputs(
    inputs, outputs, *, reference_outputs, optional=None
):
    return {"score": 1}


async def valid_mixed_positional_and_keyword_async(foo, *, bar, optional=None):
    return {"score": 1}


async def valid_mixed_positional_and_keyword_with_reference_outputs_async(
    inputs, outputs, *, reference_outputs, optional=None
):
    return {"score": 1}


def invalid_mixed_positional_and_keyword_three_args(baz, *, foo, bar, optional=None):
    return {"score": 1}


async def invalid_mixed_positional_and_keyword_three_args_async(
    baz, *, foo, bar, optional=None
):
    return {"score": 1}


# Test cases that should succeed
VALID_EVALUATOR_CASES = [
    (valid_single_supported, False),
    (valid_single_supported_async, True),
    (valid_two_arbitrary, False),
    (valid_two_arbitrary_async, True),
    (valid_multiple_supported, False),
    (valid_multiple_supported_async, True),
    (valid_mixed_positional_and_keyword, False),
    (valid_mixed_positional_and_keyword_with_reference_outputs, False),
    (valid_mixed_positional_and_keyword_async, True),
    (valid_mixed_positional_and_keyword_with_reference_outputs_async, True),
    (kwarg_valid_two_arbitrary, False),
    (kwarg_valid_two_arbitrary_async, True),
    (kwarg_valid_multiple_supported, False),
    (kwarg_valid_multiple_supported_async, True),
    (valid_additional_kwargs, False),
    (valid_additional_kwargs_async, True),
]

# Test cases that should raise ValueError
INVALID_EVALUATOR_CASES = [
    (invalid_single_unsupported, False),
    (invalid_single_unsupported_async, True),
    (invalid_three_args, False),
    (invalid_three_args_async, True),
    (kwarg_invalid_single_unsupported, False),
    (kwarg_invalid_single_unsupported_async, True),
    (kwarg_invalid_three_args, False),
    (kwarg_invalid_three_args_async, True),
    (invalid_mixed_positional_and_keyword_three_args, False),
    (invalid_mixed_positional_and_keyword_three_args_async, True),
]


def target(inputs, attachments):
    return {"foo": "bar"}


async def atarget(inputs, attachments):
    return {"foo": "bar"}


def test_passing_kwargs_is_working():
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    ds_example_responses = [_create_example(i) for i in range(10)]
    ds_examples = [e[0] for e in ds_example_responses]
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(
        ds_id, ds_name, [e[1] for e in ds_example_responses], tenant_id
    )
    session.request = fake_request.request
    client = Client(api_url="http://localhost:1984", api_key="123", session=session)
    client._tenant_id = tenant_id  # type: ignore

    def _valid_mixed_positional_and_keyword_with_reference_outputs(
        inputs, outputs, *, reference_outputs, optional=None
    ):
        assert list(inputs.keys()) == ["in"]
        assert list(outputs.keys()) == ["foo"]
        assert list(reference_outputs.keys()) == ["answer"]
        return {"score": 1}

    async def _async_valid_mixed_positional_and_keyword_with_reference_outputs(
        inputs, outputs, *, reference_outputs, optional=None
    ):
        assert list(inputs.keys()) == ["in"]
        assert list(outputs.keys()) == ["foo"]
        assert list(reference_outputs.keys()) == ["answer"]
        return {"score": 1}

    res = evaluate(
        target,
        data=ds_examples,
        evaluators=[
            _valid_mixed_positional_and_keyword_with_reference_outputs,
            _async_valid_mixed_positional_and_keyword_with_reference_outputs,
        ],
        client=client,
    )
    for r in res:
        assert r["evaluation_results"]["results"][0].score == 1
        assert r["evaluation_results"]["results"][1].score == 1


@pytest.mark.parametrize("func,is_async", VALID_EVALUATOR_CASES)
async def test_normalize_evaluator_func_valid(func, is_async):
    """Test _normalize_evaluator_func succeeds."""
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    ds_example_responses = [_create_example(i) for i in range(10)]
    ds_examples = [e[0] for e in ds_example_responses]
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(
        ds_id, ds_name, [e[1] for e in ds_example_responses], tenant_id
    )
    session.request = fake_request.request
    client = Client(api_url="http://localhost:1984", api_key="123", session=session)
    client._tenant_id = tenant_id  # type: ignore

    if is_async:
        await aevaluate(atarget, data=ds_examples, evaluators=[func], client=client)
    else:
        evaluate(target, data=ds_examples, evaluators=[func], client=client)


@pytest.mark.parametrize("func,is_async", INVALID_EVALUATOR_CASES)
def test_normalize_evaluator_func_invalid(func, is_async):
    """Test _normalize_evaluator_func fails correctly."""
    with pytest.raises(ValueError, match="Invalid evaluator function"):
        _normalize_evaluator_func(func)

    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    ds_example_responses = [_create_example(i) for i in range(10)]
    ds_examples = [e[0] for e in ds_example_responses]
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(
        ds_id, ds_name, [e[1] for e in ds_example_responses], tenant_id
    )
    session.request = fake_request.request
    client = Client(api_url="http://localhost:1984", api_key="123", session=session)
    client._tenant_id = tenant_id  # type: ignore

    with pytest.raises(ValueError, match="Invalid evaluator function"):
        if is_async:
            asyncio.run(
                aevaluate(atarget, data=ds_examples, evaluators=[func], client=client)
            )
        else:
            evaluate(target, data=ds_examples, evaluators=[func], client=client)


def summary_eval_runs_examples(runs_, examples_):
    return {"score": len(runs_[0].dotted_order)}


def summary_eval_inputs_outputs(inputs, outputs):
    return {"score": max([len(x["in"]) for x in inputs])}


def summary_eval_outputs_reference(outputs, reference_outputs):
    return min([len(x["response"]) for x in outputs])


@pytest.mark.parametrize(
    "evaluator",
    [
        summary_eval_runs_examples,
        summary_eval_inputs_outputs,
        summary_eval_outputs_reference,
    ],
)
def test__normalize_summary_evaluator(evaluator: Callable) -> None:
    normalized = _normalize_summary_evaluator(evaluator)
    runs = [
        ls_schemas.Run(
            name="foo",
            start_time=datetime.now(),
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order="a" * 12,
            outputs={"response": "c" * 12},
        )
    ]
    examples = [
        ls_schemas.Example(
            id=uuid.uuid4(),
            inputs={"in": "b" * 12},
        )
    ]
    assert normalized(runs, examples)["score"] == 12


def summary_eval_kwargs(bar, *, runs, examples):
    return


def summary_eval_unknown_positional_args(runs, examples, foo):
    return


@pytest.mark.parametrize(
    "evaluator",
    [summary_eval_kwargs, summary_eval_unknown_positional_args],
)
def test__normalize_summary_evaluator_invalid(evaluator: Callable) -> None:
    with pytest.raises(ValueError, match="Invalid evaluator function."):
        _normalize_summary_evaluator(evaluator)


def comparison_eval(runs, example):
    return [len(r.outputs["response"]) for r in runs]


def comparison_eval_simple(inputs, outputs, reference_outputs):
    return [len(o["response"]) for o in outputs]


def comparison_eval_no_inputs(outputs, reference_outputs):
    return [min(len(o["response"]), len(reference_outputs["answer"])) for o in outputs]


@pytest.mark.parametrize(
    "evaluator",
    [comparison_eval, comparison_eval_simple, comparison_eval_no_inputs],
)
def test__normalize_comparison_evaluator(evaluator: Callable) -> None:
    runs = [
        ls_schemas.Run(
            name="foo",
            start_time=datetime.now(),
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order="a",
            outputs={"response": "c" * 2},
        ),
        ls_schemas.Run(
            name="foo",
            start_time=datetime.now(),
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order="d",
            outputs={"response": "e" * 3},
        ),
    ]
    example = ls_schemas.Example(
        id=uuid.uuid4(), inputs={"in": "b"}, outputs={"answer": "f" * 4}
    )
    (normalized, _) = _normalize_comparison_evaluator_func(evaluator)
    assert normalized(runs, example) == [2, 3]


async def acomparison_eval(runs, example):
    return [len(r.outputs["response"]) for r in runs]


async def acomparison_eval_simple(inputs, outputs, reference_outputs):
    return [len(o["response"]) for o in outputs]


async def acomparison_eval_no_inputs(outputs, reference_outputs):
    return [min(len(o["response"]), len(reference_outputs["answer"])) for o in outputs]


@pytest.mark.parametrize(
    "evaluator",
    [acomparison_eval, acomparison_eval_simple, acomparison_eval_no_inputs],
)
async def test__normalize_comparison_evaluator_async(evaluator: Callable) -> None:
    runs = [
        ls_schemas.Run(
            name="foo",
            start_time=datetime.now(),
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order="a",
            outputs={"response": "c" * 2},
        ),
        ls_schemas.Run(
            name="foo",
            start_time=datetime.now(),
            run_type="chain",
            id=uuid.uuid4(),
            dotted_order="d",
            outputs={"response": "e" * 3},
        ),
    ]
    example = ls_schemas.Example(
        id=uuid.uuid4(), inputs={"in": "b"}, outputs={"answer": "f" * 4}
    )
    (normalized, _) = _normalize_comparison_evaluator_func(evaluator)
    assert await normalized(runs, example) == [2, 3]


def comparison_eval_kwargs(bar, *, runs, example):
    return


def comparison_eval_unknown_positional_args(runs, example, foo):
    return


@pytest.mark.parametrize(
    "evaluator",
    [comparison_eval_kwargs, comparison_eval_unknown_positional_args],
)
def test__normalize_comparison_evaluator_invalid(evaluator: Callable) -> None:
    with pytest.raises(ValueError, match="Invalid evaluator function."):
        _normalize_comparison_evaluator_func(evaluator)


def test_invalid_evaluate_args() -> None:
    for kwargs in [
        {"num_repetitions": 2},
        {"experiment": "foo"},
        {"upload_results": False},
        {"experiment_prefix": "foo"},
        {"data": "data"},
    ]:
        with pytest.raises(
            ValueError,
            match=(
                "Received invalid arguments. .* when target is an existing experiment."
            ),
        ):
            evaluate("foo", **kwargs)

    for kwargs in [
        {"num_repetitions": 2},
        {"experiment": "foo"},
        {"upload_results": False},
        {"summary_evaluators": [lambda a, b: 2]},
        {"data": "data"},
    ]:
        with pytest.raises(
            ValueError,
            match=(
                "Received invalid arguments. .* when target is two existing "
                "experiments."
            ),
        ):
            evaluate(("foo", "bar"), **kwargs)

    with pytest.raises(
        ValueError, match="Received invalid target. If a tuple is specified"
    ):
        evaluate(("foo", "bar", "baz"))

    with pytest.raises(ValueError, match="Received unsupported arguments"):
        evaluate((lambda x: x), data="data", load_nested=True)


async def test_invalid_aevaluate_args() -> None:
    for kwargs in [
        {"num_repetitions": 2},
        {"experiment": "foo"},
        {"upload_results": False},
        {"experiment_prefix": "foo"},
        {"data": "data"},
    ]:
        with pytest.raises(
            ValueError,
            match=(
                "Received invalid arguments. .* when target is an existing experiment."
            ),
        ):
            await aevaluate("foo", **kwargs)

    with pytest.raises(ValueError, match="Received unsupported arguments"):
        await aevaluate((lambda x: x), data="data", load_nested=True)
