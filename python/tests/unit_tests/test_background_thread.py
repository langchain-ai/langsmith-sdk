"""Unit tests for the tracing background threads."""

import gc
import threading
import time
import uuid

from langsmith._internal._background_thread import _get_hybrid_executor


def test_hybrid_executor_is_per_thread():
    """Every thread gets its own helper and keeps the same one."""
    seen = {}

    def grab(name):
        seen[name] = (_get_hybrid_executor(), _get_hybrid_executor())

    threads = [threading.Thread(target=grab, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 3
    for first, second in seen.values():
        assert first is second  # stable inside one thread
    assert len({id(first) for first, _ in seen.values()}) == 3  # distinct across


def test_hybrid_executor_retires_with_its_thread():
    """The helper's worker goes away once its owning thread exits."""
    baseline = threading.active_count()

    def use_helper():
        _get_hybrid_executor().submit(lambda: None).result()

    for _ in range(3):
        t = threading.Thread(target=use_helper)
        t.start()
        t.join()

    # Workers stop shortly after their owner is collected, so give them a moment.
    gc.collect()
    deadline = time.time() + 5
    while threading.active_count() > baseline and time.time() < deadline:
        time.sleep(0.05)

    assert threading.active_count() <= baseline


def test_hybrid_batch_sends_both_legs_when_no_helper_thread(monkeypatch):
    """If no helper thread can start, this thread sends both legs itself."""
    from queue import Queue
    from unittest.mock import MagicMock

    from langsmith._internal import _background_thread as bt
    from langsmith._internal._operations import serialize_run_dict

    class RefusesJobs:
        def submit(self, *args, **kwargs):
            raise RuntimeError("can't start new thread")

    sent = []
    monkeypatch.setattr(bt, "_get_hybrid_executor", RefusesJobs)
    monkeypatch.setattr(
        bt, "_tracing_thread_handle_batch", lambda *a, **k: sent.append("langsmith")
    )
    monkeypatch.setattr(
        bt, "_otel_tracing_thread_handle_batch", lambda *a, **k: sent.append("otel")
    )

    run_id, trace_id = uuid.uuid4(), uuid.uuid4()
    op = serialize_run_dict(
        "post",
        {
            "id": run_id,
            "trace_id": trace_id,
            "dotted_order": f"20231201T120000000000Z{trace_id}.{run_id}",
            "session_name": "test-project",
            "name": "test_run",
            "inputs": {"input": "test"},
            "run_type": "llm",
        },
    )
    item = bt.TracingQueueItem("priority", op)
    queue: Queue = Queue()
    queue.put(item)

    bt._hybrid_tracing_thread_handle_batch(
        MagicMock(), queue, [item], use_multipart=True
    )

    assert sorted(sent) == ["langsmith", "otel"]  # each leg exactly once
    assert queue.unfinished_tasks == 0  # so flush() cannot hang
