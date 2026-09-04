"""Unit tests for the tracing background threads."""

import uuid
from queue import Queue
from unittest.mock import MagicMock

from langsmith._internal import _background_thread as bt
from langsmith._internal._operations import serialize_run_dict


def test_hybrid_batch_sends_both_legs_once_and_finishes_the_queue(monkeypatch):
    """Hybrid mode sends each leg exactly once and always drains the queue."""
    sent = []
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

    assert sent == ["langsmith", "otel"]  # each leg exactly once
    assert queue.unfinished_tasks == 0  # so flush() cannot hang
