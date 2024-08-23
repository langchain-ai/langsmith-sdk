"""Test the eval runner."""

import asyncio
import json
import random
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import List
from unittest import mock
from unittest.mock import MagicMock

from langsmith import evaluate
from langsmith import schemas as ls_schemas
from langsmith.client import Client
from langsmith.evaluation._arunner import aevaluate, aevaluate_existing
from langsmith.evaluation._runner import evaluate_existing


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
                res.json.return_value = [e.dict() for e in self.ds_examples]
                return res
            elif endpoint == "http://localhost:1984/sessions":
                res = {}  # type: ignore
                if kwargs["params"]["name"] == self.created_session["name"]:  # type: ignore
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
                res.json.return_value = {"runs": list(self.runs.values())}
                return res
            elif endpoint == "http://localhost:1984/feedback":
                response = MagicMock()
                response.json.return_value = {}
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


def test_evaluate_results() -> None:
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    def _create_example(idx: int) -> ls_schemas.Example:
        return ls_schemas.Example(
            id=uuid.uuid4(),
            inputs={"in": idx},
            outputs={"answer": idx + 1},
            dataset_id=ds_id,
            created_at=datetime.now(timezone.utc),
        )

    SPLIT_SIZE = 3
    NUM_REPETITIONS = 4
    ds_examples = [_create_example(i) for i in range(10)]
    dev_split = random.sample(ds_examples, SPLIT_SIZE)
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(ds_id, ds_name, ds_examples, tenant_id)
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

        if len(ordering_of_stuff) == 3 and not locked:
            with lock:
                if len(ordering_of_stuff) == 3 and not locked:
                    locked = True
                    time.sleep(0.1)
                    slow_index = len(ordering_of_stuff)
                    ordering_of_stuff.append("predict")
                else:
                    ordering_of_stuff.append("predict")

        else:
            ordering_of_stuff.append("predict")
        return {"output": inputs["in"] + 1}

    def score_value_first(run, example):
        ordering_of_stuff.append("evaluate")
        return {"score": 0.3}

    evaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=[score_value_first],
        num_repetitions=NUM_REPETITIONS,
    )
    assert fake_request.created_session
    time.sleep(0.25)
    assert fake_request.runs
    N_PREDS = SPLIT_SIZE * NUM_REPETITIONS
    assert len(ordering_of_stuff) == N_PREDS * 2
    # Want it to be interleaved
    assert ordering_of_stuff != ["predict"] * N_PREDS + ["evaluate"] * N_PREDS
    assert slow_index is not None
    # It's delayed, so it'll be the penultimate event
    # Will run all other preds and evals, then this, then the last eval
    assert slow_index == (N_PREDS * 2) - 2

    def score_value(run, example):
        return {"score": 0.7}

    ex_results = evaluate_existing(
        fake_request.created_session["name"], evaluators=[score_value], client=client
    )
    assert len(list(ex_results)) == SPLIT_SIZE * NUM_REPETITIONS
    dev_xample_ids = [e.id for e in dev_split]
    for r in ex_results:
        assert r["example"].id in dev_xample_ids
        assert r["evaluation_results"]["results"][0].score == 0.7
        assert r["run"].reference_example_id in dev_xample_ids
    assert not fake_request.should_fail


async def test_aevaluate_results() -> None:
    session = mock.Mock()
    ds_name = "my-dataset"
    ds_id = "00886375-eb2a-4038-9032-efff60309896"

    def _create_example(idx: int) -> ls_schemas.Example:
        return ls_schemas.Example(
            id=uuid.uuid4(),
            inputs={"in": idx},
            outputs={"answer": idx + 1},
            dataset_id=ds_id,
            created_at=datetime.now(timezone.utc),
        )

    SPLIT_SIZE = 3
    NUM_REPETITIONS = 4
    ds_examples = [_create_example(i) for i in range(10)]
    dev_split = random.sample(ds_examples, SPLIT_SIZE)
    tenant_id = str(uuid.uuid4())
    fake_request = FakeRequest(ds_id, ds_name, ds_examples, tenant_id)
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

    async def predict(inputs: dict) -> dict:
        nonlocal locked
        nonlocal slow_index

        if len(ordering_of_stuff) == 3 and not locked:
            with lock:
                if len(ordering_of_stuff) == 3 and not locked:
                    locked = True
                    await asyncio.sleep(0.1)
                    slow_index = len(ordering_of_stuff)
                    ordering_of_stuff.append("predict")
                else:
                    ordering_of_stuff.append("predict")

        else:
            ordering_of_stuff.append("predict")
        return {"output": inputs["in"] + 1}

    async def score_value_first(run, example):
        ordering_of_stuff.append("evaluate")
        return {"score": 0.3}

    await aevaluate(
        predict,
        client=client,
        data=dev_split,
        evaluators=[score_value_first],
        num_repetitions=NUM_REPETITIONS,
    )
    assert fake_request.created_session
    time.sleep(0.25)
    assert fake_request.runs
    N_PREDS = SPLIT_SIZE * NUM_REPETITIONS
    assert len(ordering_of_stuff) == N_PREDS * 2
    # Want it to be interleaved
    assert ordering_of_stuff != ["predict"] * N_PREDS + ["evaluate"] * N_PREDS
    assert slow_index is not None
    # It's delayed, so it'll be the penultimate event
    # Will run all other preds and evals, then this, then the last eval
    assert slow_index == (N_PREDS * 2) - 2

    assert fake_request.created_session["name"]

    async def score_value(run, example):
        return {"score": 0.7}

    ex_results = await aevaluate_existing(
        fake_request.created_session["name"], evaluators=[score_value], client=client
    )
    all_results = [r async for r in ex_results]
    assert len(all_results) == SPLIT_SIZE * NUM_REPETITIONS
    dev_xample_ids = [e.id for e in dev_split]
    async for r in ex_results:
        assert r["example"].id in dev_xample_ids
        assert r["evaluation_results"]["results"][0].score == 0.7
        assert r["run"].reference_example_id in dev_xample_ids
    assert not fake_request.should_fail
