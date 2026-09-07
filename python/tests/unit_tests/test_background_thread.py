"""Unit tests for the tracing background threads."""

import threading
from queue import Queue

from bench.hybrid_tracing import FakeClient, make_batches
from langsmith._internal import _background_thread as bt


def test_hybrid_mode_spawns_no_threads_per_batch(monkeypatch):
    """Handling a batch must not start OS threads.

    Brittle on purpose. If a change adds a helper thread back to this path, this
    fails and the trade-off gets discussed instead of the churn creeping back.
    Counting starts rather than comparing threading.active_count() matters: a
    helper that is joined before the handler returns leaves the count unchanged.
    """
    started: list[str] = []
    real_start = threading.Thread.start

    def counting_start(self):
        started.append(self.name)
        return real_start(self)

    monkeypatch.setattr(threading.Thread, "start", counting_start)

    client = FakeClient()
    for batch in make_batches(20, ops_per_batch=5):
        bt._hybrid_tracing_thread_handle_batch(
            client, Queue(), batch, use_multipart=True, mark_task_done=False
        )

    assert client.sends == 20  # the sends really happened
    assert started == []  # and cost no threads


def test_hybrid_batch_sends_both_legs_once_and_finishes_the_queue(monkeypatch):
    """Hybrid mode sends each leg exactly once and always drains the queue."""
    sent = []
    monkeypatch.setattr(
        bt, "_tracing_thread_handle_batch", lambda *a, **k: sent.append("langsmith")
    )
    monkeypatch.setattr(
        bt, "_otel_tracing_thread_handle_batch", lambda *a, **k: sent.append("otel")
    )

    batch = make_batches(1, ops_per_batch=1)[0]
    queue: Queue = Queue()
    queue.put(batch[0])

    bt._hybrid_tracing_thread_handle_batch(FakeClient(), queue, batch, True)

    assert sent == ["langsmith", "otel"]  # each leg exactly once
    assert queue.unfinished_tasks == 0  # so flush() cannot hang
