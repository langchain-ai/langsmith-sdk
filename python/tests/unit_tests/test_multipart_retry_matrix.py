"""Retry matrix for multipart ingestion.

This is the executable spec for *what gets retried and how many times* when
``POST /runs/multipart`` fails. Two independent layers decide that:

1. urllib3 ``Retry`` mounted on the session adapter (``_default_retry_config``):
   ``status_forcelist=[502, 503, 504, 408, 425]`` plus a second, easy-to-miss
   trigger -- ``respect_retry_after_header`` makes 413/429/503 retryable *only*
   when the response actually carries a ``Retry-After`` header.
2. The ``for idx in range(1, attempts + 1)`` loop in ``_send_multipart_req``,
   which retries only ``LangSmithConnectionError`` / ``LangSmithRequestTimeout``
   / ``LangSmithAPIError`` (500) and swallows everything else.

A ``MagicMock`` session cannot see layer 1 at all, so these tests drive a real
local HTTP server through the real adapter and count sockets hit.
"""

import json
import logging
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pytest

from langsmith import utils as ls_utils
from langsmith._internal._multipart import join_multipart_parts_and_context
from langsmith._internal._operations import (
    SerializedRunOperation,
    serialized_run_operation_to_multipart_parts_and_context,
)
from langsmith.client import Client


class _Endpoint:
    """A stand-in /runs/multipart that returns a canned status and counts hits."""

    def __init__(self):
        self.count = 0
        self.status = 200
        self.retry_after = None
        self.url = ""


@pytest.fixture
def endpoint(socket_enabled):
    ep = _Endpoint()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):  # noqa: N802
            # Drain the body first, otherwise the client sees a reset rather
            # than the status code we are trying to exercise.
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            elif self.headers.get("Transfer-Encoding") == "chunked":
                while True:
                    size = int(self.rfile.readline().strip() or b"0", 16)
                    self.rfile.read(size + 2)
                    if size == 0:
                        break
            ep.count += 1
            body = b"{}"
            self.send_response(ep.status)
            if ep.retry_after is not None:
                self.send_header("Retry-After", str(ep.retry_after))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    ep.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield ep
    server.shutdown()
    server.server_close()


@pytest.fixture
def no_sleep():
    """Keep urllib3's backoff decisions, drop the wall-clock cost."""
    with mock.patch("urllib3.util.retry.time.sleep") as slept:
        yield slept


def _payload(n_runs=1):
    """Build a payload through the real serializer, so the log context is real.

    The per-op context string is ``trace=<trace_id>,id=<run_id>``
    (``_operations.py``), and ``join_multipart_parts_and_context`` concatenates
    one of those per operation with ``"; "``. Hand-writing the context in a test
    would pin a message shape that never occurs in production.
    """
    ops = []
    ids = []
    for _ in range(n_runs):
        run_id = uuid.uuid4()
        ids.append(run_id)
        run_json = json.dumps(
            {
                "id": str(run_id),
                "name": "test_run",
                "run_type": "chain",
                "trace_id": str(run_id),
                "dotted_order": str(run_id),
            }
        ).encode()
        ops.append(
            SerializedRunOperation(
                operation="post",
                id=run_id,
                trace_id=run_id,
                _none=run_json,
                inputs=None,
                outputs=None,
                events=None,
                extra=None,
                error=None,
                serialized=None,
                attachments=None,
            )
        )
    parts = [
        serialized_run_operation_to_multipart_parts_and_context(op)[0] for op in ops
    ]
    return join_multipart_parts_and_context(parts), ids


def _one_run_payload():
    return _payload(1)[0]


def _client(endpoint, failed_traces_dir=None, monkeypatch=None):
    ls_utils.get_env_var.cache_clear()
    if failed_traces_dir is not None:
        monkeypatch.setenv("LANGSMITH_FAILED_TRACES_DIR", str(failed_traces_dir))
    return Client(api_url=endpoint.url, api_key="test", auto_batch_tracing=False)


# (status, retry_after_header, expected_requests, retried_by)
RETRY_MATRIX = [
    # Terminal successes -- one shot.
    (200, None, 1, "none"),
    # 409 is treated as a duplicate/no-op and breaks immediately.
    (409, None, 1, "none"),
    # Only *exactly* 500 maps to LangSmithAPIError -> app-layer loop (3 attempts).
    (500, None, 3, "app loop"),
    # In status_forcelist -> urllib3 retries 3x, app loop then gives up.
    (502, None, 4, "urllib3"),
    (503, None, 4, "urllib3"),
    (504, None, 4, "urllib3"),
    (425, None, 4, "urllib3"),
    # 408 is the only status in BOTH layers: 4 requests x 3 app attempts.
    (408, None, 12, "urllib3 + app loop"),
    # 429 is NOT in status_forcelist, but IS in Retry.RETRY_AFTER_STATUS_CODES,
    # so the header alone decides whether it is retried at all.
    #
    # TODO: a 429 with no Retry-After is dropped after a single attempt. Neither
    # the smith-go /runs/multipart route (no ratelimit middleware on the chi
    # router) nor the load balancer sets Retry-After, so in practice rate-limited
    # ingest traffic is thrown away rather than backed off. Fix by adding 429 to
    # `status_forcelist` in `_default_retry_config` so it is retried with the
    # normal backoff when the header is absent, and/or by making the server send
    # Retry-After. When that lands, the (429, None) row below becomes 4 and this
    # test will fail loudly -- update the row, don't delete it.
    (429, 1, 4, "urllib3 (Retry-After only)"),
    (429, None, 1, "none"),
    # Same conditional mechanism applies to 413.
    (413, 1, 4, "urllib3 (Retry-After only)"),
    (413, None, 1, "none"),
    # Plain client errors are never retried.
    (401, None, 1, "none"),
    (403, None, 1, "none"),
    (404, None, 1, "none"),
    (422, None, 1, "none"),
]


@pytest.mark.parametrize(
    "status,retry_after,expected_requests,retried_by",
    RETRY_MATRIX,
    ids=[f"{s}{'+retry-after' if ra else ''}" for s, ra, _, _ in RETRY_MATRIX],
)
def test_multipart_retry_counts(
    endpoint, no_sleep, status, retry_after, expected_requests, retried_by
):
    """Pin the exact number of POSTs each failure mode produces."""
    endpoint.status = status
    endpoint.retry_after = retry_after
    client = _client(endpoint)

    client._send_multipart_req(_one_run_payload())

    assert endpoint.count == expected_requests, (
        f"HTTP {status} (Retry-After={retry_after}) produced {endpoint.count} "
        f"requests, expected {expected_requests} (retried by: {retried_by})"
    )


def test_retry_after_header_value_drives_the_delay(endpoint, no_sleep):
    """429 retries honour Retry-After, not ``backoff_factor``.

    The (429, ...) rows in RETRY_MATRIX already pin *whether* the header enables
    retries at all -- 1 request without it, 4 with. This covers the part a
    request count cannot see: the delay comes from the header (2s), not from
    ``backoff_factor=0.5``.
    """
    endpoint.status = 429
    endpoint.retry_after = 2
    client = _client(endpoint)

    client._send_multipart_req(_one_run_payload())

    assert no_sleep.call_args_list, (
        "429 carrying Retry-After was not retried at all, so no backoff happened"
    )
    assert no_sleep.call_args_list[-1].args[0] == pytest.approx(2, abs=0.01)


def test_app_loop_does_not_back_off(endpoint, no_sleep):
    """The 3 app-layer attempts for a 500 fire back-to-back with no delay.

    500 is not in the forcelist, so urllib3 never sleeps; the app loop is a bare
    `continue`. Zero sleeps for the three requests RETRY_MATRIX already counts.
    """
    endpoint.status = 500
    client = _client(endpoint)

    client._send_multipart_req(_one_run_payload())

    assert no_sleep.call_count == 0


@pytest.mark.parametrize(
    "status,dumped",
    [
        (200, False),
        (409, False),  # swallowed as a duplicate -- silently dropped, no dump
        (500, True),
        (429, True),
        (404, True),
    ],
)
def test_exhausted_batch_is_dropped_not_requeued(
    endpoint, no_sleep, tmp_path, monkeypatch, status, dumped
):
    """Once retries stop, the batch is gone unless LANGSMITH_FAILED_TRACES_DIR is set.

    Nothing re-enqueues it: ``_tracing_thread_handle_batch`` calls
    ``task_done()`` for every item in a ``finally``.
    """
    endpoint.status = status
    client = _client(endpoint, failed_traces_dir=tmp_path, monkeypatch=monkeypatch)

    client._send_multipart_req(_one_run_payload())

    files = list(tmp_path.iterdir())
    assert bool(files) is dumped
    ls_utils.get_env_var.cache_clear()


def test_no_failed_traces_dir_means_silent_data_loss(endpoint, no_sleep, monkeypatch):
    """Default config (no fallback dir): an exhausted batch is lost with a warning."""
    monkeypatch.delenv("LANGSMITH_FAILED_TRACES_DIR", raising=False)
    endpoint.status = 500
    errors = []
    ls_utils.get_env_var.cache_clear()
    client = Client(
        api_url=endpoint.url,
        api_key="test",
        auto_batch_tracing=False,
        tracing_error_callback=errors.append,
    )

    client._send_multipart_req(_one_run_payload())

    # Nothing on disk, and the only programmatic signal is the error callback.
    assert len(errors) == 1
    assert isinstance(errors[0], ls_utils.LangSmithAPIError)


# ---------------------------------------------------------------------------
# The warning log is the ONLY customer-visible signal that traces were dropped
# (the error callback is opt-in, the fallback dir is opt-in). These tests pin
# its exact wording.
# ---------------------------------------------------------------------------


def _only_warning(caplog):
    """Return the single warning emitted for a dropped batch.

    Asserting the count here covers every caller: retries are silent, so three
    POSTs for a 500 still produce exactly one warning, not one per attempt.
    """
    msgs = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == "langsmith.client"
    ]
    assert len(msgs) == 1, f"expected exactly one warning, got {len(msgs)}: {msgs}"
    return msgs[0]


def test_warning_message_when_retries_exhausted(endpoint, no_sleep, caplog):
    """Exact message for a retryable failure that ran out of attempts (500).

    The ``\\)`` running straight into ``trace=`` is not a typo: ``_context`` is
    concatenated with no separator. Pinned here so fixing it is deliberate.
    """
    caplog.set_level(logging.WARNING, logger="langsmith.client")
    endpoint.status = 500
    client = _client(endpoint)

    acc, (run_id,) = _payload(1)
    client._send_multipart_req(acc)

    msg = _only_warning(caplog)
    assert re.fullmatch(
        r"Failed to multipart ingest runs: "
        r"Server error \(500\) caused failure to POST "
        r"http://127\.0\.0\.1:\d+/runs/multipart in LangSmith API\. "
        r"HTTPError\('500 Server Error: .*?', '\{\}'\)"
        rf"trace={run_id},id={run_id}",
        msg,
    ), msg


def test_warning_message_when_not_retryable(endpoint, no_sleep, caplog):
    """Exact message for a non-retryable failure (429 with no Retry-After).

    Note this path formats the exception differently from the exhausted-retry
    path above: it goes through ``traceback.format_exception_only``, so the
    fully-qualified exception class name leaks into the customer-facing log.
    """
    caplog.set_level(logging.WARNING, logger="langsmith.client")
    endpoint.status = 429
    endpoint.retry_after = None
    client = _client(endpoint)

    acc, (run_id,) = _payload(1)
    client._send_multipart_req(acc)

    msg = _only_warning(caplog)
    assert re.fullmatch(
        r"Failed to multipart ingest runs: "
        r"langsmith\.utils\.LangSmithRateLimitError: "
        r"Rate limit exceeded for http://127\.0\.0\.1:\d+/runs/multipart\. "
        r"HTTPError\('429 Client Error: .*?', '\{\}'\)"
        rf"trace={run_id},id={run_id}",
        msg,
    ), msg


def test_warning_lists_every_run_in_the_batch(endpoint, no_sleep, caplog):
    """A batch failure names ALL its runs, not the one that "failed".

    There is no single failing run: the whole POST failed, so the whole batch is
    dropped. ``join_multipart_parts_and_context`` concatenates one
    ``trace=<t>,id=<r>`` per operation with ``"; "``, so the warning grows
    linearly with batch size -- up to the default 100-op limit, roughly 8KB of
    UUIDs on one log line.
    """
    caplog.set_level(logging.WARNING, logger="langsmith.client")
    endpoint.status = 500
    client = _client(endpoint)

    acc, ids = _payload(3)
    client._send_multipart_req(acc)

    msg = _only_warning(caplog)
    for run_id in ids:
        assert f"trace={run_id},id={run_id}" in msg
    assert msg.count("trace=") == 3
    assert "; " in msg, "per-op contexts are joined with '; '"


@pytest.mark.xfail(
    reason=(
        "Customer-clarity gaps in the drop warning. The message never states "
        "that the runs were DISCARDED, how many were lost, that no further "
        "retry will happen, or that LANGSMITH_FAILED_TRACES_DIR can capture "
        "them. It is also logged at WARNING rather than ERROR despite being "
        "unrecoverable data loss."
    ),
    strict=False,
)
def test_warning_message_is_explicit_about_data_loss(endpoint, no_sleep, caplog):
    caplog.set_level(logging.WARNING, logger="langsmith.client")
    endpoint.status = 500
    client = _client(endpoint)

    client._send_multipart_req(_one_run_payload())

    (record,) = [
        r
        for r in caplog.records
        if r.name == "langsmith.client" and r.levelno >= logging.WARNING
    ]
    msg = record.getMessage().lower()

    assert record.levelno >= logging.ERROR, "unrecoverable data loss should be ERROR"
    assert "1 run" in msg, "should say how many runs were lost"
    assert any(w in msg for w in ("dropped", "discarded", "lost")), (
        "should say the data is gone"
    )
    assert "will not be retried" in msg, "should say retries are over"
    assert "langsmith_failed_traces_dir" in msg, "should point at the mitigation"
