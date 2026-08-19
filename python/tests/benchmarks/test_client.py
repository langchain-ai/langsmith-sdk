"""Benchmarks for `Client` run ingestion.

`create_run` is the entry point every integration funnels into. With batching
enabled it must serialize the run and enqueue it fast enough to stay off the
caller's critical path; the queue drain then does the batching and upload work.
"""

from queue import PriorityQueue

from langsmith._internal._background_thread import (
    _tracing_thread_drain_queue,
    _tracing_thread_handle_batch,
)
from langsmith.client import Client
from tests.benchmarks._payloads import create_run_payload, mock_session


def _client(**kwargs) -> Client:
    return Client(session=mock_session(), api_key="fake", **kwargs)


def _create_runs(client: Client, runs: list) -> None:
    for run in runs:
        client.create_run(**run)


def test_create_run_unbatched(benchmark):
    """Direct, synchronous `create_run` calls (auto-batching disabled)."""
    client = _client(auto_batch_tracing=False)
    runs = [create_run_payload(20) for _ in range(20)]
    benchmark(_create_runs, client, runs)


def test_create_run_enqueue(benchmark):
    """The latency the caller actually pays when batching is on."""
    client = _client(auto_batch_tracing=False)
    client.tracing_queue = PriorityQueue()
    runs = [create_run_payload(20) for _ in range(20)]
    benchmark(_create_runs, client, runs)


def _drain_queue(client: Client) -> None:
    assert client.tracing_queue is not None
    while next_batch := _tracing_thread_drain_queue(
        client.tracing_queue, limit=100, block=False
    ):
        _tracing_thread_handle_batch(
            client, client.tracing_queue, next_batch, use_multipart=True
        )


def test_enqueue_and_drain_tracing_queue(benchmark):
    """Full batched path: enqueue 50 runs, then drain them as the thread does."""
    client = _client(auto_batch_tracing=False)
    runs = [create_run_payload(20) for _ in range(50)]

    def setup_and_drain() -> None:
        client.tracing_queue = PriorityQueue()
        for run in runs:
            client.create_run(**run)
        _drain_queue(client)

    benchmark(setup_and_drain)
