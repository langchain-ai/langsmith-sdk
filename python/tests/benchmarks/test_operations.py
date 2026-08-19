"""Benchmarks for the run-ingestion pipeline.

Between `client.create_run` and the HTTP request, every run is turned into a
`SerializedRunOperation`, merged with its pending patches, encoded as multipart
and zstd-compressed. This is what the background tracing thread spends its time
on, and it is the part that back-pressures the user's application when it is
too slow.
"""

import uuid

import pytest

from langsmith._internal._compressed_traces import CompressedTraces
from langsmith._internal._operations import (
    combine_serialized_queue_operations,
    compress_multipart_parts_and_context,
    serialize_run_dict,
    serialized_run_operation_to_multipart_parts_and_context,
)
from tests.benchmarks._payloads import create_run_payload

BOUNDARY = "----boundary-for-benchmarks"


def _payloads(n: int, json_size: int) -> list:
    return [create_run_payload(json_size) for _ in range(n)]


def _serialize_many(payloads: list) -> list:
    return [serialize_run_dict("post", dict(p)) for p in payloads]


@pytest.mark.parametrize("json_size", [10, 200])
def test_serialize_run_dict(benchmark, json_size):
    payloads = _payloads(20, json_size)
    benchmark(_serialize_many, payloads)


def test_combine_serialized_queue_operations(benchmark):
    """Post + patch pairs for the same run get merged before upload."""
    payloads = _payloads(50, 10)
    posts = [serialize_run_dict("post", dict(p)) for p in payloads]
    patches = [serialize_run_dict("patch", dict(p)) for p in payloads]
    ops = [op for pair in zip(posts, patches) for op in pair]
    benchmark(combine_serialized_queue_operations, ops)


def _to_multipart(ops: list) -> None:
    for op in ops:
        serialized_run_operation_to_multipart_parts_and_context(op)


def test_run_operation_to_multipart(benchmark):
    ops = _serialize_many(_payloads(20, 50))
    benchmark(_to_multipart, ops)


def _compress(parts_list: list) -> None:
    compressed = CompressedTraces()
    for parts in parts_list:
        compress_multipart_parts_and_context(parts, compressed, BOUNDARY)


def test_compress_multipart(benchmark):
    ops = _serialize_many(_payloads(10, 50))
    parts_list = [
        serialized_run_operation_to_multipart_parts_and_context(op)[0] for op in ops
    ]
    benchmark(_compress, parts_list)


def _full_pipeline(payloads: list) -> None:
    ops = [serialize_run_dict("post", dict(p)) for p in payloads]
    ops = combine_serialized_queue_operations(ops)
    compressed = CompressedTraces()
    for op in ops:
        parts, _ = serialized_run_operation_to_multipart_parts_and_context(op)
        compress_multipart_parts_and_context(parts, compressed, BOUNDARY)


def test_ingestion_pipeline_end_to_end(benchmark):
    """Serialize -> combine -> multipart -> compress, as the tracing thread does."""
    payloads = _payloads(10, 50)
    benchmark(_full_pipeline, payloads)


def _deserialize(ops: list) -> None:
    for op in ops:
        op.deserialize_run_info()


def test_deserialize_run_info(benchmark):
    ops = _serialize_many(_payloads(50, 10))
    benchmark(_deserialize, ops)


def test_calculate_serialized_size(benchmark):
    ops = _serialize_many(_payloads(50, 10))
    benchmark(lambda: [op.calculate_serialized_size() for op in ops])


def test_serialize_run_dict_with_uuid_ids(benchmark):
    payloads = _payloads(20, 10)
    for payload in payloads:
        payload["id"] = uuid.UUID(payload["id"])
        payload["trace_id"] = uuid.UUID(payload["trace_id"])
    benchmark(_serialize_many, payloads)
