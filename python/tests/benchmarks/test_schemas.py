"""Benchmarks for parsing API payloads into the SDK schemas.

Reading data back from LangSmith (listing runs, fetching examples for an
evaluation) goes through Pydantic validation of these models, which dominates the
cost of large `list_runs` / `list_examples` calls.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from langsmith import schemas as ls_schemas


def _run_payloads(count: int) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    payloads = []
    for i in range(count):
        run_id = str(uuid4())
        payloads.append(
            {
                "id": run_id,
                "trace_id": run_id,
                "name": f"run_{i}",
                "run_type": "llm",
                "start_time": now,
                "end_time": now,
                "inputs": {"messages": [{"role": "user", "content": f"hi {i}"}]},
                "outputs": {"generations": [{"text": f"hello {i}"}]},
                "extra": {"metadata": {"ls_model_name": "gpt-4o-mini"}},
                "events": [{"name": "start", "time": now}],
                "tags": ["a", "b"],
                "session_id": str(uuid4()),
                "status": "success",
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "total_cost": "0.0001",
                "dotted_order": f"20240101T000000000000Z{run_id}",
            }
        )
    return payloads


def _example_payloads(count: int) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    dataset_id = str(uuid4())
    return [
        {
            "id": str(uuid4()),
            "dataset_id": dataset_id,
            "created_at": now,
            "modified_at": now,
            "inputs": {"question": f"question {i}"},
            "outputs": {"answer": f"answer {i}"},
            "metadata": {"split": "train"},
        }
        for i in range(count)
    ]


@pytest.mark.benchmark
def test_parse_runs(benchmark):
    payloads = _run_payloads(200)

    def run() -> None:
        for payload in payloads:
            ls_schemas.Run(**payload)

    benchmark(run)


@pytest.mark.benchmark
def test_parse_examples(benchmark):
    payloads = _example_payloads(500)

    def run() -> None:
        for payload in payloads:
            ls_schemas.Example(**payload)

    benchmark(run)


@pytest.mark.benchmark
def test_dump_runs(benchmark):
    runs = [ls_schemas.Run(**payload) for payload in _run_payloads(200)]

    def run() -> None:
        for run_obj in runs:
            run_obj.model_dump(exclude_none=True)

    benchmark(run)
