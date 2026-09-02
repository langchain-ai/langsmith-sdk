"""Every resend of a multipart batch must carry its file attachments.

Covers both layers that can resend one body:

* our own attempt loop in ``Client._send_multipart_req`` (per attempt, per write
  endpoint), and
* urllib3's status retries, which run *beneath* that loop because
  ``_default_retry_config`` force-lists 429/500/502/503/504/408/425 and resends
  the same body object.

A ``MultipartEncoder`` is single-use, so without a rewindable body a resend
ships a run with an empty attachment under an already-declared
``Content-Length``: the server either stores an attachment-less run or stalls
waiting for bytes that never arrive.
"""

import base64
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pytest
import urllib3

from langsmith import utils as ls_utils
from langsmith._internal._constants import _BOUNDARY
from langsmith._internal._multipart import (
    RewindableMultipartBody,
    join_multipart_parts_and_context,
)
from langsmith._internal._operations import (
    SerializedRunOperation,
    serialized_run_operation_to_multipart_parts_and_context,
)
from langsmith.client import Client

ATTACHMENT = b"A" * 50_000


class _Sink:
    """Records what each POST actually delivered."""

    def __init__(self):
        self.url = ""
        self.status = 200
        self.received = []  # dicts: declared, received, intact, chunked


def _serve(sink):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        # A body that declares Content-Length and then sends nothing would hang
        # the read; time out instead so the test records the truncation.
        timeout = 2

        def do_POST(self):  # noqa: N802
            declared = int(self.headers.get("Content-Length") or 0)
            body = self._read_body(declared)
            sink.received.append(
                {
                    "declared": declared,
                    "received": len(body),
                    "intact": ATTACHMENT in body,
                    "chunked": "chunked"
                    in (self.headers.get("Transfer-Encoding") or ""),
                }
            )
            payload = b"{}"
            self.send_response(sink.status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_body(self, declared):
            chunks, remaining = [], declared
            while remaining > 0:
                try:
                    chunk = self.rfile.read(min(remaining, 65_536))
                except (TimeoutError, OSError):
                    break
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.001}, daemon=True
    ).start()
    sink.url = f"http://127.0.0.1:{server.server_address[1]}"
    return server


@pytest.fixture
def sink(socket_enabled):
    s = _Sink()
    server = _serve(s)
    yield s
    server.shutdown()
    server.server_close()


@pytest.fixture
def no_backoff():
    """Keep urllib3's retry *count* but drop its wall-clock backoff.

    Patching the sleep away rather than the ``Retry`` object matters: the
    transport-level resend is the behaviour under test, so it has to stay.
    """
    retry = urllib3.util.retry.Retry
    with (
        mock.patch.object(retry, "get_backoff_time", return_value=0),
        mock.patch.object(retry, "get_retry_after", return_value=None),
    ):
        yield


@pytest.fixture
def attachment_batch(tmp_path):
    """Build a one-run batch whose attachment is a *path*, so parts hold a handle.

    Production closes those handles in ``_multipart_ingest_ops``' ``finally``
    (via ``_close_files``); these tests drive ``_send_multipart_req`` directly
    and so bypass it, which is why the fixture owns them. Leaving them open
    trips ResourceWarning under the ``PYTHONDEVMODE=1`` that ``make test`` sets.
    """
    opened_handles = []

    def build():
        path = tmp_path / "attachment.bin"
        path.write_bytes(ATTACHMENT)
        run_id = uuid.uuid4()
        op = SerializedRunOperation(
            operation="post",
            id=run_id,
            trace_id=run_id,
            _none=json.dumps(
                {
                    "id": str(run_id),
                    "name": "test_run",
                    "run_type": "chain",
                    "trace_id": str(run_id),
                    "dotted_order": str(run_id),
                }
            ).encode(),
            inputs=None,
            outputs=None,
            events=None,
            error=None,
            extra=None,
            serialized=None,
            attachments={"blob": ("application/octet-stream", str(path))},
        )
        parts, opened = serialized_run_operation_to_multipart_parts_and_context(op)
        assert opened, "attachment should have been opened as a file handle"
        opened_handles.extend(opened.values())
        return join_multipart_parts_and_context([parts])

    yield build

    for handle in opened_handles:
        handle.close()


def _assert_all_intact(received, label):
    assert received, f"{label}: no request reached the endpoint"
    bad = [r for r in received if not r["intact"]]
    assert not bad, (
        f"{label}: {len(bad)}/{len(received)} resends lost the attachment: {received}"
    )
    # A resend of a consumed stream also breaks the length contract: either it
    # declares the full size and delivers less, or it falls back to chunked.
    assert all(r["declared"] == r["received"] for r in received), received
    assert not any(r["chunked"] for r in received), received
    assert len({r["received"] for r in received}) == 1, received


@pytest.mark.parametrize(
    # 0 forces every body over the threshold, i.e. the streamed branch that
    # hands the encoder itself to requests.
    "max_inline_bytes",
    [20_000_000, 0],
    ids=["inline-bytes", "streamed"],
)
def test_every_retry_keeps_the_file_attachment(
    sink, no_backoff, attachment_batch, max_inline_bytes
):
    """500 drives both retry layers; every resulting request must be complete.

    ``_send_multipart_req`` runs 3 attempts and urllib3 force-lists 500, so one
    call produces several sends of the same batch. Attempt 1 used to be the only
    one carrying the attachment.
    """
    sink.status = 500
    ls_utils.get_env_var.cache_clear()
    client = Client(api_url=sink.url, api_key="test", auto_batch_tracing=False)

    with mock.patch("langsmith.client._MULTIPART_INLINE_MAX_BYTES", max_inline_bytes):
        client._send_multipart_req(attachment_batch())

    # More sends than app attempts proves urllib3 resent the body itself, which
    # is the layer our attempt loop cannot rewind for.
    assert len(sink.received) > 3, sink.received
    _assert_all_intact(sink.received, "app + transport retries")


def test_every_write_endpoint_gets_the_file_attachment(
    socket_enabled, attachment_batch
):
    """The second replica must not receive an attachment-less copy.

    ``_send_multipart_req`` loops over ``_write_api_urls`` and re-encodes per
    endpoint, so this fails on the *happy path* -- no error, no retry, replica 2
    simply stores a run missing its attachment.
    """
    first, second = _Sink(), _Sink()
    s1, s2 = _serve(first), _serve(second)
    try:
        ls_utils.get_env_var.cache_clear()
        client = Client(
            api_urls={first.url: "key-1", second.url: "key-2"},
            auto_batch_tracing=False,
        )
        assert len(client._write_api_urls) == 2

        client._send_multipart_req(attachment_batch())

        _assert_all_intact(first.received, "first endpoint")
        _assert_all_intact(second.received, "second endpoint")
        assert first.received[0]["received"] == second.received[0]["received"]
    finally:
        s1.shutdown()
        s1.server_close()
        s2.shutdown()
        s2.server_close()


def test_failed_trace_dump_keeps_the_file_attachment(
    sink, no_backoff, attachment_batch, tmp_path, monkeypatch
):
    """The on-disk fallback copy must be replayable, i.e. carry the attachment.

    The dump encodes the parts a final time after every send has read them, so
    without a rewind the dumped payload is a run with an empty attachment --
    and replaying it would silently commit the data loss.
    """
    sink.status = 500
    monkeypatch.setenv("LANGSMITH_FAILED_TRACES_DIR", str(tmp_path))
    ls_utils.get_env_var.cache_clear()
    client = Client(api_url=sink.url, api_key="test", auto_batch_tracing=False)

    try:
        client._send_multipart_req(attachment_batch())

        dumps = list(tmp_path.glob("trace_*.json"))
        assert len(dumps) == 1, f"expected one dumped trace, got {dumps}"
        envelope = json.loads(dumps[0].read_text())
        body = base64.b64decode(envelope["body_base64"])
        assert ATTACHMENT in body, "dumped trace lost its attachment"
    finally:
        ls_utils.get_env_var.cache_clear()


def test_rewindable_body_replays_byte_for_byte(attachment_batch):
    """The contract urllib3 relies on: ``tell``/``seek(0)`` and a stable length.

    urllib3 records ``tell()`` before sending and calls ``seek()`` with it
    before a resend; ``requests`` sizes ``Content-Length`` from ``len()`` once.
    """
    parts = attachment_batch().parts
    body = RewindableMultipartBody(parts, _BOUNDARY)

    total = len(body)
    assert body.tell() == 0
    first = body.read()
    assert len(first) == total
    assert ATTACHMENT in first
    assert body.tell() == total
    assert body.read() == b"", "encoder should be exhausted"

    assert body.seek(0) == 0
    assert body.tell() == 0
    assert len(body) == total, "length must not shift across a rewind"
    assert body.read() == first, "replay must be byte-identical"

    body.seek(0)
    assert body.to_bytes() == first

    with pytest.raises(OSError):
        body.seek(1)
