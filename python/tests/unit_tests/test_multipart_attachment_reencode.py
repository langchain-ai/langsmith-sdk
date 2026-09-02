import base64
import json
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

ATTACHMENT = b"A" * 50_000


class _Sink:
    """Records what each POST actually delivered."""

    def __init__(self):
        self.url = ""
        self.status = 200
        self.received = []  # (body_len, attachment_intact)


def _serve(sink):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            sink.received.append((len(body), ATTACHMENT in body))
            payload = b"{}"
            self.send_response(sink.status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

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
def no_sleep():
    """Drop backoff wall-clock cost; these tests only care about bytes sent."""
    with mock.patch("urllib3.util.retry.time.sleep"):
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
            extra=None,
            error=None,
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


@pytest.mark.parametrize(
    # 0 forces every body over the threshold, i.e. the streamed branch.
    "max_inline_bytes",
    [20_000_000, 0],
    ids=["inline-bytes", "streamed"],
)
def test_app_loop_retry_keeps_the_file_attachment(
    sink, no_sleep, attachment_batch, max_inline_bytes
):
    """Every retry must resend the attachment, not just the first attempt.

    500 drives ``_send_multipart_req``'s app loop through all 3 attempts. Each
    one re-encodes the same parts, so attempts 2 and 3 are the regression: they
    used to ship the run without its attachment and a server would store it.

    Both size branches are covered: under the threshold the encoder is drained
    into bytes up front, over it the encoder itself is handed to requests and
    read during the send.
    """
    sink.status = 500
    ls_utils.get_env_var.cache_clear()
    client = Client(api_url=sink.url, api_key="test", auto_batch_tracing=False)

    with mock.patch("langsmith.client._MULTIPART_INLINE_MAX_BYTES", max_inline_bytes):
        client._send_multipart_req(attachment_batch())

    assert sink.received, "no request reached the endpoint"
    assert all(intact for _size, intact in sink.received), (
        "an attempt shipped a run whose attachment had been silently dropped: "
        f"{sink.received}"
    )
    # All bodies identical in size -- nothing was quietly truncated.
    assert len({size for size, _ in sink.received}) == 1, sink.received


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

        for name, s in (("first", first), ("second", second)):
            assert s.received, f"{name} endpoint received nothing"
            assert all(intact for _size, intact in s.received), (
                f"{name} endpoint got a run with the attachment dropped: {s.received}"
            )
        assert [size for size, _ in first.received] == [
            size for size, _ in second.received
        ]
    finally:
        s1.shutdown()
        s1.server_close()
        s2.shutdown()
        s2.server_close()


def test_failed_trace_dump_keeps_the_file_attachment(
    sink, no_sleep, attachment_batch, tmp_path, monkeypatch
):
    """The on-disk fallback copy must be replayable, i.e. carry the attachment.

    ``_dump_body`` re-encodes the parts a final time after every send has read
    them, so without a rewind the dumped payload is a run with an empty
    attachment -- and replaying it would silently commit the data loss.
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
