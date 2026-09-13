"""Compressed ingestion for replicas that carry their own credentials (R2).

A zstd frame is POSTed verbatim to each of its destinations, so every op inside one
frame must share the same destination set. These tests pin that invariant, the
credential resolution behind it, and that nothing crosses between destinations.
"""

import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest
import zstandard

from langsmith import schemas as ls_schemas
from langsmith._internal import _background_thread as bt
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith._internal._operations import (
    SerializedFeedbackOperation,
    SerializedRunOperation,
)
from langsmith.client import (
    Client,
    ReplicaAuth,
    _apply_auth_overrides,
    _duplicate_op,
)
from langsmith.run_trees import RunTree

_INFO = ls_schemas.LangSmithInfo(
    version="0.8.11",
    batch_ingest_config=ls_schemas.BatchIngestConfig(use_multipart_endpoint=True),
)


def _replica(api_url, api_key, project_name=None):
    replica = {"api_url": api_url, "auth": {"api_key": api_key}}
    if project_name:
        replica["project_name"] = project_name
    return replica


class Harness:
    """A client whose frame is real but whose queue and network are captured.

    The background threads are off, so nothing drains concurrently and the
    assertions are deterministic.
    """

    def __init__(self, **client_kwargs):
        client_kwargs.setdefault("api_url", "https://own")
        client_kwargs.setdefault("api_key", "own-key")
        self.client = Client(
            session=MagicMock(), auto_batch_tracing=False, info=_INFO, **client_kwargs
        )
        self.client.compressed_traces = CompressedTraces()
        self.client._data_available_event = threading.Event()
        self.client.tracing_queue = MagicMock()  # exists, so the fallback is live
        self.queued: list = []
        self.sent: list = []
        # Patched with lambdas, not bound methods: a bound method assigned to a
        # class attribute is not a descriptor, so `self` would not be passed and
        # every argument would shift by one.
        self._patches = [
            patch.object(
                Client,
                "request_with_retries",
                lambda _self, _method, url, **kwargs: self._record(url, kwargs),
            ),
            patch.object(
                Client,
                "_put_tracing_queue",
                lambda _self, item: self.queued.append(item),
            ),
        ]

    def _record(self, url, kwargs):
        body = kwargs["request_kwargs"].get("data")
        if isinstance(body, bytes):
            raw = body
        elif hasattr(body, "getvalue"):
            raw = body.getvalue()
        else:
            raw = b""
        headers = kwargs["request_kwargs"].get("headers", {})
        self.sent.append((url, headers.get("x-api-key"), raw))

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()

    def post(self, replicas=None, project_name="proj", inputs=None):
        run = RunTree(
            name="r",
            run_type="chain",
            inputs=inputs if inputs is not None else {"a": 1},
            ls_client=self.client,
            project_name=project_name,
            replicas=replicas,
        )
        run.post()
        return run

    def flush(self):
        stream, info, destinations = bt._tracing_thread_drain_compressed_buffer(
            self.client, size_limit=1, size_limit_bytes=1
        )
        if stream is not None:
            self.client._send_compressed_multipart_req(
                stream, info, destinations=destinations
            )

    @property
    def routes(self):
        return sorted((url, key) for url, key, _ in self.sent)

    def frame_for(self, url_prefix):
        """The decompressed body of the frame sent to a destination."""
        raw = next(r for u, _, r in self.sent if u.startswith(url_prefix))
        return zstandard.ZstdDecompressor().decompressobj().decompress(raw)


# --- routing -----------------------------------------------------------------


def test_credentialed_replica_is_compressed_to_its_own_destination():
    with Harness() as h:
        h.post([_replica("https://b", "kb")])
        h.flush()
    assert h.routes == [("https://b/runs/multipart", "kb")]
    assert not h.queued


def test_replicas_sharing_auth_share_one_frame():
    with Harness() as h:
        h.post([_replica("https://b", "kb", "p1"), _replica("https://b", "kb", "p2")])
        assert h.client.compressed_traces.trace_count == 2
        h.flush()
    assert h.routes == [("https://b/runs/multipart", "kb")]
    assert not h.queued


def test_replica_naming_the_clients_own_credentials_shares_the_frame():
    with Harness() as h:
        h.post([{"project_name": "p1"}, _replica("https://own", "own-key", "p2")])
        assert h.client.compressed_traces.trace_count == 2
        h.flush()
    assert h.routes == [("https://own/runs/multipart", "own-key")]
    assert not h.queued


def test_nothing_crosses_between_destinations():
    """The assertion that would have caught #2013."""
    with Harness() as h:
        h.post(
            [_replica("https://b", "kb", "mine"), _replica("https://d", "kd", "theirs")]
        )
        h.flush()

    assert {u: k for u, k, _ in h.sent} == {"https://b/runs/multipart": "kb"}
    assert [(i.api_url, i.api_key) for i in h.queued] == [("https://d", "kd")]

    body = h.frame_for("https://b")
    assert b"mine" in body
    assert b"theirs" not in body
    assert b"kd" not in body and b"https://d" not in body


def test_post_and_patch_for_one_destination_take_the_same_transport():
    with Harness() as h:
        run = h.post(
            [_replica("https://b", "kb", "p1"), _replica("https://d", "kd", "p2")]
        )
        run.end(outputs={"b": 2})
        run.patch()
        assert h.client.compressed_traces.trace_count == 2  # B's post and patch
        h.flush()
    assert h.routes == [("https://b/runs/multipart", "kb")]
    assert [(i.api_url, i.api_key) for i in h.queued] == [("https://d", "kd")] * 2


# --- ownership ---------------------------------------------------------------


def test_a_fixed_replica_list_keeps_a_stable_outcome():
    """Frames release their destinations when sent, but the result must not churn.

    `post()` writes in replica-list order, so with an unchanged list the same set
    claims every new frame and the other consistently uses the queue. A run's post
    and patch therefore stay on one transport.
    """
    pair = [_replica("https://b", "kb", "p1"), _replica("https://d", "kd", "p2")]
    with Harness() as h:
        h.post(pair)
        h.flush()
        assert len(h.queued) == 1
        for _ in range(3):
            h.post(pair)
            h.flush()
    assert {u for u, _, _ in h.sent} == {"https://b/runs/multipart"}
    assert [i.api_url for i in h.queued] == ["https://d"] * 4


def test_a_replica_only_client_is_never_challenged():
    with Harness() as h:
        for _ in range(3):
            h.post([_replica("https://b", "kb")])
        assert h.client.compressed_traces.trace_count == 3
        h.flush()
    assert h.routes == [("https://b/runs/multipart", "kb")]
    assert not h.queued


def test_an_open_frame_holds_its_destinations_and_a_sent_one_releases_them():
    dest_b = frozenset({ReplicaAuth(api_url="https://b", api_key="kb")})
    dest_d = frozenset({ReplicaAuth(api_url="https://d", api_key="kd")})
    traces = CompressedTraces()

    # unclaimed: anything may enter
    assert traces.accepts(dest_b) and traces.accepts(dest_d)

    # claimed: only its own destinations, or the frame would be mis-delivered
    traces.destinations = dest_b
    assert traces.accepts(dest_b)
    assert not traces.accepts(dest_d)

    # sent: released, so a client whose replicas changed is not stuck on dest_b
    traces.reset()
    assert traces.destinations is None
    assert traces.accepts(dest_d)


def test_replicas_that_change_can_claim_the_next_frame():
    with Harness() as h:
        h.post([_replica("https://b", "kb")])
        h.flush()
        h.post([_replica("https://d", "kd")])
        assert h.client.compressed_traces.trace_count == 1
        h.flush()
    assert h.routes == [
        ("https://b/runs/multipart", "kb"),
        ("https://d/runs/multipart", "kd"),
    ]
    assert not h.queued


def test_a_second_destination_set_still_waits_for_the_next_frame():
    with Harness() as h:
        h.post([_replica("https://b", "kb", "p1"), _replica("https://d", "kd", "p2")])
        assert h.client.compressed_traces.trace_count == 1
        assert [i.api_url for i in h.queued] == ["https://d"]


# --- feedback ----------------------------------------------------------------


def test_feedback_is_kept_out_of_a_replica_owned_frame():
    with Harness() as h:
        run = h.post([_replica("https://b", "kb")])
        h.client.create_feedback(run.id, key="score", score=1.0, trace_id=run.trace_id)
        assert h.client.compressed_traces.trace_count == 1  # the run only
        h.flush()
    assert h.routes == [("https://b/runs/multipart", "kb")]
    assert [type(i.item).__name__ for i in h.queued] == ["SerializedFeedbackOperation"]
    assert b"feedback" not in h.frame_for("https://b")


def test_feedback_shares_the_frame_when_no_replica_owns_it():
    with Harness() as h:
        run = h.post()
        h.client.create_feedback(run.id, key="score", score=1.0, trace_id=run.trace_id)
        assert h.client.compressed_traces.trace_count == 2
        h.flush()
    assert h.routes == [("https://own/runs/multipart", "own-key")]
    assert not h.queued


# --- credential resolution ---------------------------------------------------


def _headers_for(client, destinations):
    return sorted(
        (
            d.api_url,
            tuple(
                sorted(
                    _apply_auth_overrides(
                        {**client._headers},
                        api_key=d.api_key,
                        service_key=d.service_key,
                        tenant_id=d.tenant_id,
                        authorization=d.authorization,
                        cookie=d.cookie,
                        fallback_api_key=None,
                    ).items()
                )
            ),
        )
        for d in destinations
    )


@pytest.mark.parametrize(
    "auth",
    [
        ReplicaAuth(),
        ReplicaAuth(api_key="replica-key"),
        ReplicaAuth(api_url="https://b"),
        ReplicaAuth(service_key="svc"),
        ReplicaAuth(authorization="Bearer t"),
        ReplicaAuth(cookie="c=1"),
        ReplicaAuth(api_url="https://b", api_key="kb"),
    ],
    ids=[
        "none",
        "api_key",
        "api_url",
        "service_key",
        "authorization",
        "cookie",
        "both",
    ],
)
def test_resolution_matches_the_headers_the_old_paths_would_have_sent(auth):
    client = Client(
        api_url="https://own",
        api_key="own-key",
        session=MagicMock(),
        auto_batch_tracing=False,
    )
    if not any(auth):
        expected = [
            (url, key, None, None, None, None)
            for url, key in client._write_api_urls.items()
        ]
        fallback = None
    else:
        expected = [auth]
        fallback = client.api_key
    want = sorted(
        (
            a[0] or client.api_url,
            tuple(
                sorted(
                    _apply_auth_overrides(
                        {**client._headers},
                        api_key=a[1],
                        service_key=a[2],
                        tenant_id=a[3],
                        authorization=a[4],
                        cookie=a[5],
                        fallback_api_key=fallback,
                    ).items()
                )
            ),
        )
        for a in expected
    )
    assert _headers_for(client, client._resolve_destinations(auth)) == want


def test_a_null_write_api_url_key_still_strips_the_api_key_header():
    client = Client(
        api_urls={"https://a": ""}, session=MagicMock(), auto_batch_tracing=False
    )
    destinations = client._resolve_destinations(ReplicaAuth())
    assert [d.api_key for d in destinations] == [""]


def test_service_key_replica_sends_no_api_key():
    with Harness() as h:
        h.post([{"api_url": "https://b", "auth": {"service_key": "svc"}}])
        h.flush()
    assert h.routes == [("https://b/runs/multipart", None)]


def test_two_keys_for_one_host_stay_distinct_destinations():
    """Identical payloads, different tenants: one frame, one send per key.

    Destinations come from resolved auth, so the two keys are never merged into
    one destination. A merge would be invisible here -- the payloads do match.
    """
    with Harness() as h:
        h.post([_replica("https://same", "key-1"), _replica("https://same", "key-2")])
        assert h.client.compressed_traces.trace_count == 1
        h.flush()
    assert h.routes == [
        ("https://same/runs/multipart", "key-1"),
        ("https://same/runs/multipart", "key-2"),
    ]
    assert not h.queued


# --- non-regression ----------------------------------------------------------


def test_multiple_write_api_urls_still_replay_one_frame():
    with Harness(api_url=None, api_urls={"https://a": "ka", "https://b": "kb"}) as h:
        h.post()
        h.flush()
    assert h.routes == [
        ("https://a/runs/multipart", "ka"),
        ("https://b/runs/multipart", "kb"),
    ]
    assert h.sent[0][2] == h.sent[1][2] and h.sent[0][2]
    assert not h.queued


def test_project_only_replicas_are_unchanged():
    with Harness() as h:
        h.post([{"project_name": "p1"}, {"project_name": "p2"}])
        assert h.client.compressed_traces.trace_count == 2
        h.flush()
    assert h.routes == [("https://own/runs/multipart", "own-key")]
    assert not h.queued


# --- resources and security --------------------------------------------------


def test_multipart_files_are_closed_whether_or_not_the_op_is_admitted():
    """The close must not sit on the accept path only -- that would leak fds."""
    from langsmith import client as client_module

    closed: list = []
    with (
        Harness() as h,
        patch.object(client_module, "_close_files", lambda files: closed.append(files)),
    ):
        h.post([_replica("https://b", "kb")])  # admitted
        assert len(closed) == 1
        h.post([_replica("https://d", "kd")])  # rejected -> queue
        assert len(closed) == 1, "rejected op never reached the compressed path"
        h.post([_replica("https://b", "kb")])  # admitted again
    assert len(closed) == 2


def test_replica_auth_never_renders_a_credential():
    auth = ReplicaAuth(
        api_url="https://x",
        api_key="sk-secret",
        service_key="svc-secret",
        tenant_id="tenant-1",
        authorization="Bearer tok",
        cookie="c=v",
    )
    secrets = ["sk-secret", "svc-secret", "Bearer tok", "c=v"]
    for rendered in (
        repr(auth),
        str(auth),
        f"{auth}",
        "%s" % (auth,),
        "%r" % (auth,),
        repr(frozenset({auth})),
        repr({"dest": auth}),
    ):
        for secret in secrets:
            assert secret not in rendered, rendered
    assert "https://x" in repr(auth)
    assert "api_key" in repr(auth)  # which fields are set is still visible


def test_admission_under_concurrency_never_mixes_destinations():
    with Harness() as h:
        stop = threading.Event()
        drains: list = []

        def drain_loop():
            while not stop.is_set():
                stream, info, destinations = bt._tracing_thread_drain_compressed_buffer(
                    h.client, size_limit=1, size_limit_bytes=1
                )
                if stream is not None:
                    drains.append((destinations, stream.getvalue()))

        drainer = threading.Thread(target=drain_loop)
        drainer.start()
        writers = [
            threading.Thread(
                target=lambda i=i: [
                    h.post(
                        [
                            _replica("https://b", "kb", "mine"),
                            _replica("https://d", "kd", "theirs"),
                        ],
                        inputs={"n": i},
                    )
                    for _ in range(10)
                ]
            )
            for i in range(4)
        ]
        for w in writers:
            w.start()
        for w in writers:
            w.join()
        stop.set()
        drainer.join()
        h.flush()

    assert drains, "expected at least one frame to be drained mid-flight"
    for destinations, raw in drains:
        urls = {d.api_url for d in destinations}
        assert urls == {"https://b"}, urls
        body = zstandard.ZstdDecompressor().decompressobj().decompress(raw)
        assert b"theirs" not in body


# --- payload grouping (step 2) ------------------------------------------------


class _CountSerializations:
    """Count serialize_run_dict calls inside the block."""

    def __enter__(self):
        from langsmith import client as client_module

        self.calls: list = []
        original = client_module.serialize_run_dict

        def spy(*args, **kwargs):
            self.calls.append(1)
            return original(*args, **kwargs)

        self._patch = patch.object(client_module, "serialize_run_dict", spy)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()

    def __len__(self):
        return len(self.calls)


def test_identical_replicas_are_serialized_once():
    with Harness() as h, _CountSerializations() as count:
        h.post([_replica("https://a", "ka"), _replica("https://b", "kb")])
    assert len(count) == 1


def test_one_frame_reaches_every_destination_with_its_own_key():
    with Harness() as h:
        h.post([_replica("https://a", "ka"), _replica("https://b", "kb")])
        assert h.client.compressed_traces.trace_count == 1
        h.flush()
    assert h.routes == [
        ("https://a/runs/multipart", "ka"),
        ("https://b/runs/multipart", "kb"),
    ]
    assert h.sent[0][2] == h.sent[1][2] and h.sent[0][2]
    assert not h.queued


def test_grouped_ops_share_bytes_but_are_distinct_objects():
    with Harness() as h:
        h.post([_replica("https://x", "kx")])  # takes the frame
        h.post([_replica("https://a", "ka"), _replica("https://b", "kb")])
    assert len(h.queued) == 2
    first, second = (item.item for item in h.queued)
    assert first is not second
    assert first._none is second._none
    assert first.inputs is second.inputs


def test_duplicating_an_op_shares_bytes_but_not_the_attachments_dict():
    op = SerializedRunOperation(
        "post",
        uuid.uuid4(),
        uuid.uuid4(),
        b"none-blob",
        inputs=b"in-blob",
        attachments={"a": ("text/plain", b"x")},
    )
    duplicate = _duplicate_op(op)

    assert duplicate is not op
    assert duplicate._none is op._none
    assert duplicate.inputs is op.inputs
    assert duplicate.attachments is not op.attachments
    assert duplicate.attachments == op.attachments

    # combine_serialized_queue_operations does exactly this, per auth group.
    duplicate.attachments.update({"b": ("text/plain", b"y")})
    assert "b" not in op.attachments


def test_duplicating_an_op_without_attachments_is_safe():
    op = SerializedFeedbackOperation(uuid.uuid4(), uuid.uuid4(), b"f")
    duplicate = _duplicate_op(op)
    assert duplicate is not op
    assert duplicate.feedback is op.feedback


def test_a_rejected_group_reaches_every_destination_by_queue():
    with Harness() as h:
        h.post([_replica("https://x", "kx")])
        h.post([_replica("https://a", "ka"), _replica("https://b", "kb")])
    assert [(i.api_url, i.api_key) for i in h.queued] == [
        ("https://a", "ka"),
        ("https://b", "kb"),
    ]


# One test per field of the grouping key: each must NOT group.


def test_replicas_with_different_projects_are_not_grouped():
    with Harness() as h, _CountSerializations() as count:
        h.post([_replica("https://a", "ka", "p1"), _replica("https://b", "kb", "p2")])
    assert len(count) == 2


def test_replicas_with_different_updates_are_not_grouped():
    with Harness() as h, _CountSerializations() as count:
        h.post(
            [
                {
                    "api_url": "https://a",
                    "auth": {"api_key": "ka"},
                    "updates": {"tags": ["x"]},
                },
                {"api_url": "https://b", "auth": {"api_key": "kb"}},
            ]
        )
    assert len(count) == 2


def test_primary_false_is_not_the_same_as_primary_absent():
    with Harness() as h, _CountSerializations() as count:
        h.post(
            [
                {"api_url": "https://a", "auth": {"api_key": "ka"}, "primary": False},
                {"api_url": "https://b", "auth": {"api_key": "kb"}},
            ]
        )
    assert len(count) == 2


def test_replicas_on_different_clients_are_not_grouped():
    with Harness() as h, _CountSerializations() as count:
        other = Client(
            api_url="https://own",
            api_key="own-key",
            session=MagicMock(),
            auto_batch_tracing=False,
            info=_INFO,
        )
        other.tracing_queue = MagicMock()  # so it serializes instead of POSTing
        h.post(
            [
                {"api_url": "https://a", "auth": {"api_key": "ka"}},
                {"api_url": "https://b", "auth": {"api_key": "kb"}, "client": other},
            ]
        )
    assert len(count) == 2


# --- the non-batch path (no compression, no queue) -----------------------------


def _non_batch_client():
    client = Client(
        api_url="https://own",
        api_key="own-key",
        session=MagicMock(),
        auto_batch_tracing=False,
    )
    assert client.tracing_queue is None and client.compressed_traces is None
    return client


def test_non_batch_writes_reach_the_replica_destination():
    client = _non_batch_client()
    sent: list = []
    with patch.object(
        Client,
        "request_with_retries",
        lambda _s, _m, url, **kw: sent.append(
            (url, kw["request_kwargs"]["headers"].get("x-api-key"))
        ),
    ):
        run = RunTree(
            name="r",
            run_type="chain",
            inputs={"a": 1},
            ls_client=client,
            project_name="proj",
            replicas=[_replica("https://b", "kb")],
        )
        run.post()
        run.end(outputs={"b": 2})
        run.patch()
    assert [key for _, key in sent] == ["kb", "kb"]
    assert all(url.startswith("https://b/") for url, _ in sent), sent


def test_non_batch_writes_reach_every_destination_of_a_group():
    client = _non_batch_client()
    sent: list = []
    with patch.object(
        Client,
        "request_with_retries",
        lambda _s, _m, url, **kw: sent.append(
            (url, kw["request_kwargs"]["headers"].get("x-api-key"))
        ),
    ):
        RunTree(
            name="r",
            run_type="chain",
            inputs={"a": 1},
            ls_client=client,
            project_name="proj",
            replicas=[_replica("https://a", "ka"), _replica("https://b", "kb")],
        ).post()
    assert sorted(sent) == [
        ("https://a/runs", "ka"),
        ("https://b/runs", "kb"),
    ]
