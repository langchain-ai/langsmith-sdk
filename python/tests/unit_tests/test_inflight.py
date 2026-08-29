from __future__ import annotations

import threading
import time
import uuid
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from langsmith import utils as ls_utils
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _tracing_thread_handle_batch,
)
from langsmith._internal._constants import _TRACING_MAX_INFLIGHT_BYTES
from langsmith._internal._inflight import TracingBytesLimiter
from langsmith._internal._operations import SerializedFeedbackOperation
from langsmith.client import Client


def test_limiter_blocks_until_bytes_are_released() -> None:
    limiter = TracingBytesLimiter(10)
    entered = threading.Event()

    def wait_for_capacity() -> None:
        with limiter.limit(6):
            entered.set()

    with limiter.limit(6):
        thread = threading.Thread(target=wait_for_capacity)
        thread.start()
        assert not entered.wait(0.05)
    assert entered.wait(1)
    thread.join()


def test_limiter_allows_oversized_batch_to_run_alone() -> None:
    limiter = TracingBytesLimiter(10)
    entered = threading.Event()

    def run_oversized() -> None:
        with limiter.limit(100):
            entered.set()

    with limiter.limit(1):
        thread = threading.Thread(target=run_oversized)
        thread.start()
        assert not entered.wait(0.05)
    assert entered.wait(1)
    thread.join()


def test_limiter_releases_bytes_after_exception() -> None:
    limiter = TracingBytesLimiter(10)

    with pytest.raises(RuntimeError), limiter.limit(10):
        raise RuntimeError("upload failed")

    with limiter.limit(10):
        pass


def test_batch_handler_limits_concurrent_upload_bytes() -> None:
    active = 0
    peak_active = 0
    lock = threading.Lock()
    release = threading.Event()

    def ingest(*args, **kwargs) -> None:
        nonlocal active, peak_active
        with lock:
            active += 1
            peak_active = max(peak_active, active)
        release.wait(timeout=1)
        with lock:
            active -= 1

    client = SimpleNamespace(
        _tracing_inflight_limiter=TracingBytesLimiter(4),
        _multipart_ingest_ops=ingest,
        _invoke_tracing_error_callback=lambda error: None,
    )

    def make_batch(priority: str) -> list[TracingQueueItem]:
        operation = SerializedFeedbackOperation(
            id=uuid.uuid4(), trace_id=uuid.uuid4(), feedback=b"1234"
        )
        return [TracingQueueItem(priority, operation)]

    threads = [
        threading.Thread(
            target=_tracing_thread_handle_batch,
            args=(client, Queue(), make_batch(str(index)), True),
            kwargs={"mark_task_done": False},
        )
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    time.sleep(0.05)
    release.set()
    for thread in threads:
        thread.join()

    assert peak_active == 1


@pytest.mark.parametrize(
    ("argument", "environment", "expected"),
    [
        (1234, None, 1234),
        (None, "5678", 5678),
        (None, None, _TRACING_MAX_INFLIGHT_BYTES),
        (0, "5678", 0),
    ],
)
def test_client_resolves_inflight_trace_byte_limit(
    argument: int | None, environment: str | None, expected: int
) -> None:
    values = {"LANGSMITH_API_KEY": "test-key"}
    if environment is not None:
        values["LANGSMITH_TRACING_MAX_INFLIGHT_BYTES"] = environment
    ls_utils.get_env_var.cache_clear()
    with (
        patch.dict("os.environ", values, clear=True),
        patch("langsmith.client._tracing_control_thread_func"),
    ):
        client = Client(max_inflight_trace_bytes=argument)

    assert client._tracing_inflight_limiter.capacity == expected
    client.cleanup(timeout=0)


def test_client_rejects_invalid_inflight_trace_byte_limit() -> None:
    ls_utils.get_env_var.cache_clear()
    with patch.dict(
        "os.environ",
        {
            "LANGSMITH_API_KEY": "test-key",
            "LANGSMITH_TRACING_MAX_INFLIGHT_BYTES": "many",
        },
        clear=True,
    ):
        with pytest.raises(ValueError, match="must be an integer"):
            Client()


def test_disabled_limiter_does_not_serialize_callers() -> None:
    limiter = TracingBytesLimiter(0)
    barrier = threading.Barrier(3)

    def enter() -> None:
        with limiter.limit(100):
            barrier.wait(timeout=1)
            time.sleep(0.01)

    threads = [threading.Thread(target=enter) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=1)
    for thread in threads:
        thread.join()
