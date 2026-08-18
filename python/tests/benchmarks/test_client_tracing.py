"""Benchmarks for the client-side tracing pipeline.

These cover the work done between `client.create_run(...)` and the bytes handed
over to the transport: run serialization, queue draining, operation combination,
multipart encoding and zstd compression.
"""

from queue import PriorityQueue
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from langsmith._internal._background_thread import (
    _tracing_thread_drain_queue,
    _tracing_thread_handle_batch,
)
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith._internal._constants import _BOUNDARY
from langsmith._internal._operations import (
    combine_serialized_queue_operations,
    compress_multipart_parts_and_context,
    encode_multipart_parts_and_context,
    serialize_run_dict,
    serialized_run_operation_to_multipart_parts_and_context,
)


def _payload(size: int) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "user", "content": f"This is message number {i}"}
            for i in range(size)
        ],
        "metadata": {"ls_model_name": "gpt-4o-mini", "ls_provider": "openai"},
    }


def _run_dicts(num_runs: int, payload_size: int = 20) -> List[Dict[str, Any]]:
    return [
        {
            "name": "Run Name",
            "id": str(uuid4()),
            "run_type": "chain",
            "inputs": _payload(payload_size),
            "outputs": _payload(payload_size),
            "extra": {"metadata": {"revision_id": "abc"}},
            "trace_id": "trace_id",
            "dotted_order": "1.1",
            "tags": ["tag1", "tag2"],
            "session_name": "Session Name",
        }
        for _ in range(num_runs)
    ]


@pytest.mark.benchmark
def test_create_run_inline(benchmark, client):
    runs = _run_dicts(100)

    def run() -> None:
        for run_dict in runs:
            client.create_run(**dict(run_dict))

    benchmark(run)


@pytest.mark.benchmark
def test_batch_ingest_runs(benchmark, client):
    runs = _run_dicts(100)

    def run() -> None:
        client.batch_ingest_runs(create=[dict(r) for r in runs])

    benchmark(run)


@pytest.mark.benchmark
def test_tracing_queue_drain_and_send(benchmark, client):
    runs = _run_dicts(100)

    def run() -> None:
        client.tracing_queue = PriorityQueue()
        for run_dict in runs:
            client.create_run(**dict(run_dict))
        while next_batch := _tracing_thread_drain_queue(
            client.tracing_queue, limit=100, block=False
        ):
            _tracing_thread_handle_batch(
                client, client.tracing_queue, next_batch, use_multipart=True
            )

    benchmark(run)


@pytest.mark.benchmark
def test_serialize_run_dict(benchmark):
    runs = _run_dicts(100)

    def run() -> None:
        for run_dict in runs:
            serialize_run_dict("post", dict(run_dict))

    benchmark(run)


@pytest.mark.benchmark
def test_combine_serialized_queue_operations(benchmark):
    creates = [serialize_run_dict("post", dict(r)) for r in _run_dicts(100)]
    updates = [
        serialize_run_dict(
            "patch",
            {
                "id": op.id,
                "trace_id": op.trace_id,
                "outputs": _payload(5),
                "end_time": "2024-10-22T19:00:00Z",
            },
        )
        for op in creates
    ]
    ops = [*creates, *updates]

    benchmark(lambda: combine_serialized_queue_operations(list(ops)))


@pytest.mark.benchmark
def test_encode_multipart_parts(benchmark):
    parts = [
        serialized_run_operation_to_multipart_parts_and_context(
            serialize_run_dict("post", dict(r))
        )[0]
        for r in _run_dicts(50)
    ]

    def run() -> None:
        for part in parts:
            for _ in encode_multipart_parts_and_context(part, _BOUNDARY):
                pass

    benchmark(run)


@pytest.mark.benchmark
def test_compress_multipart_parts(benchmark):
    parts = [
        serialized_run_operation_to_multipart_parts_and_context(
            serialize_run_dict("post", dict(r))
        )[0]
        for r in _run_dicts(50)
    ]

    def run() -> None:
        compressed_traces = CompressedTraces()
        for part in parts:
            compress_multipart_parts_and_context(part, compressed_traces, _BOUNDARY)

    benchmark(run)
