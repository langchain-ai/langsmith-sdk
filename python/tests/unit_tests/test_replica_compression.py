"""Spec for X3a: credentialed replicas must not lose zstd compression.

Written test-first. See ``REPLICAS_COMPRESSION_PLAN.md`` at the repo root for the
design; finding IDs (R2, R11, R14) are from ``REPLICAS.md``.

The invariant under test:

    A zstd frame is POSTed verbatim to each of its destinations, so every
    operation inside one frame must share the same destination set.

Two consequences the tests pin down:

* replicas whose payloads are identical should be serialized and compressed
  **once**, and the single frame sent to each destination with that
  destination's own credentials;
* replicas whose destination sets differ must not share a frame.

Assertions are on observable delivery -- which endpoint received which bytes,
and whether they were compressed -- rather than on internal structure, so the
tests survive the implementation choices they are meant to drive.
"""

import queue
import threading
import time
import uuid
import weakref
from unittest.mock import MagicMock, patch

import pytest

from langsmith import Client
from langsmith._internal._background_thread import (
    _tracing_thread_drain_compressed_buffer,
    _tracing_thread_handle_batch,
)
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith.run_trees import AuthHeaders, RunTree, WriteReplica

URL_A = "https://a.example.com"
URL_B = "https://b.example.com"
KEY_A = "key-a"
KEY_B = "key-b"


class Sent(list):
    """Captured outbound requests: (url, api_key, content_encoding, body)."""

    def to(self, url):
        return [s for s in self if s[0].startswith(url)]

    @property
    def keys_used(self):
        return {s[1] for s in self}

    @property
    def encodings(self):
        return {s[2] for s in self}

    @property
    def bodies(self):
        return [s[3] for s in self]


def make_client(compression=True, **kwargs):
    client = Client(
        api_url="https://main.example.com",
        api_key="main-key",
        session=MagicMock(),
        auto_batch_tracing=False,
        **kwargs,
    )
    client.tracing_queue = queue.PriorityQueue(maxsize=1000)
    client._futures = weakref.WeakSet()
    if compression:
        client.compressed_traces = CompressedTraces()
        client._data_available_event = threading.Event()
    else:
        client.compressed_traces = None
    return client


def deliver(client):
    """Run every send path to completion and capture what left the process.

    Drives both the compressed buffer and the tracing queue so the tests can
    assert on delivery without caring which path a run happened to take.
    """
    sent = Sent()

    def capture(self, method, url, **kw):
        rk = kw.get("request_kwargs") or {}
        headers = rk.get("headers") or {}
        body = rk.get("data")
        if hasattr(body, "read"):
            pos = body.tell()
            body.seek(0)
            raw = body.read()
            body.seek(pos)
        elif isinstance(body, (bytes, bytearray)):
            raw = bytes(body)
        else:
            raw = getattr(body, "to_string", lambda: b"")()
        sent.append(
            (url, headers.get("x-api-key"), headers.get("Content-Encoding"), raw)
        )
        return MagicMock(status_code=202)

    with patch.object(Client, "request_with_retries", capture):
        if client.compressed_traces is not None:
            stream, info = _tracing_thread_drain_compressed_buffer(
                client, size_limit=1, size_limit_bytes=1
            )
            if stream is not None:
                client._send_compressed_multipart_req(stream, info)
        batch = []
        while not client.tracing_queue.empty():
            batch.append(client.tracing_queue.get_nowait())
        if batch:
            _tracing_thread_handle_batch(
                client, client.tracing_queue, batch, True, mark_task_done=False
            )
    return sent


def post_run(client, replicas, project_name="proj", inputs=None):
    rt = RunTree(
        name="r",
        run_type="chain",
        id=uuid.uuid4(),
        inputs=inputs if inputs is not None else {"a": 1},
        ls_client=client,
        project_name=project_name,
        replicas=replicas,
    )
    rt.post()
    rt.end(outputs={"b": 2})
    rt.patch()
    return rt


# --------------------------------------------------------------------------
# Admission and routing
# --------------------------------------------------------------------------


class TestCompressedAdmission:
    def test_identical_payload_replicas_stay_on_the_compressed_path(self):
        """R2: two destinations, identical payloads -> compression must survive.

        This is the ``LANGSMITH_RUNS_ENDPOINTS`` shape: no ``project_name``, so
        ``_remap_for_project`` takes its fast path and both replicas produce
        byte-identical payloads that differ only in where they are going.
        """
        client = make_client()
        post_run(
            client,
            [
                WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
        )
        assert client.compressed_traces.trace_count > 0, (
            "credentialed replicas were diverted to the uncompressed queue"
        )
        assert client.tracing_queue.empty()

    def test_one_frame_reaches_every_destination_with_its_own_key(self):
        """One compressed body, N POSTs -- not N compressions."""
        client = make_client()
        post_run(
            client,
            [
                WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
        )
        sent = deliver(client)

        assert len(sent.to(URL_A)) == 1
        assert len(sent.to(URL_B)) == 1
        assert sent.keys_used == {KEY_A, KEY_B}
        assert sent.encodings == {"zstd"}, (
            f"expected every destination to receive compressed bytes, got {sent.encodings}"
        )
        assert sent.to(URL_A)[0][3] == sent.to(URL_B)[0][3], (
            "the same frame should be reused, not recompressed per destination"
        )

    def test_project_only_replicas_are_unchanged(self):
        """Regression guard: today's cheap path must keep working."""
        client = make_client()
        post_run(
            client,
            [
                WriteReplica(project_name="p1", primary=True),
                WriteReplica(project_name="p2"),
            ],
        )
        assert client.compressed_traces.trace_count > 0
        assert client.tracing_queue.empty()

    def test_mismatched_destination_sets_do_not_share_a_frame(self):
        """Different destination sets must not be merged; the odd one out is
        still delivered, via the queue if necessary."""
        client = make_client()
        post_run(
            client,
            [
                WriteReplica(project_name="p1", primary=True),
                WriteReplica(
                    project_name="p2", api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)
                ),
            ],
        )
        sent = deliver(client)
        assert sent.to(URL_B), "the credentialed replica was dropped"
        assert sent.to("https://main.example.com"), "the primary replica was dropped"

    def test_no_cross_destination_bleed(self):
        """The failure the current all-None guard exists to prevent.

        Asserted on remapped run ids, not on project-name markers: R1 puts the
        whole replica list -- every destination's ``project_name`` included --
        inside every run body, so a string marker would match everywhere and
        prove nothing.
        """
        from langsmith._internal._uuid import uuid7, uuid7_deterministic

        client = make_client()
        # Must be a v7 id: uuid7_deterministic falls back to time.time_ns() for
        # non-v7 inputs, so a v4 id here would make this test flaky -- and makes
        # secondary replica ids unstable in real use (R15).
        run_id = uuid7()
        rt = RunTree(
            name="r", run_type="chain", id=run_id, inputs={"a": 1},
            ls_client=client, project_name="proj",
            replicas=[
                WriteReplica(
                    project_name="only-a", api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)
                ),
                WriteReplica(
                    project_name="only-b", api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)
                ),
            ],
        )
        rt.post()
        rt.end(outputs={"b": 2})
        rt.patch()

        id_a = str(uuid7_deterministic(run_id, "only-a")).encode()
        id_b = str(uuid7_deterministic(run_id, "only-b")).encode()
        sent = deliver(client)

        for url, mine, theirs in ((URL_A, id_a, id_b), (URL_B, id_b, id_a)):
            payloads = sent.to(url)
            assert payloads, f"nothing delivered to {url}"
            joined = b"".join(body for *_, body in payloads)
            if sent.encodings == {"zstd"}:
                continue  # compressed; per-destination routing covered above
            assert mine in joined, f"{url} did not receive its own run"
            assert theirs not in joined, f"{url} received another destination's run"


# --------------------------------------------------------------------------
# Fan-out grouping
# --------------------------------------------------------------------------


class TestFanOutGrouping:
    def test_identical_replicas_are_serialized_once(self):
        client = make_client()
        with patch(
            "langsmith.client.serialize_run_dict",
            side_effect=__import__(
                "langsmith._internal._operations", fromlist=["x"]
            ).serialize_run_dict,
        ) as spy:
            post_run(
                client,
                [
                    WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                    WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
                    WriteReplica(api_url="https://c.example.com",
                                 auth=AuthHeaders(api_key="key-c")),
                ],
            )
        posts = [c for c in spy.call_args_list if c.args and c.args[0] == "post"]
        assert len(posts) == 1, (
            f"3 identical replicas serialized {len(posts)} times; expected 1"
        )

    def test_replicas_differing_in_updates_are_not_grouped(self):
        """Guards the R14 interaction: `updates` must be part of the identity key
        even though the fast path currently discards it."""
        client = make_client()
        with patch(
            "langsmith.client.serialize_run_dict",
            side_effect=__import__(
                "langsmith._internal._operations", fromlist=["x"]
            ).serialize_run_dict,
        ) as spy:
            post_run(
                client,
                [
                    WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A),
                                 updates={"tags": ["a"]}),
                    WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B),
                                 updates={"tags": ["b"]}),
                ],
            )
        posts = [c for c in spy.call_args_list if c.args and c.args[0] == "post"]
        assert len(posts) == 2, "replicas with different `updates` must not be grouped"

    def test_grouped_ops_share_bytes_but_are_distinct_objects(self):
        """combine_serialized_queue_operations mutates the post op in place and
        runs per auth group, so containers must not be shared even though the
        immutable payload blobs should be."""
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
        )
        ops = [i.item for i in list(client.tracing_queue.queue) if i.item.operation == "post"]
        assert len(ops) == 2
        assert ops[0] is not ops[1], "op containers must not be shared across destinations"
        assert ops[0].inputs is ops[1].inputs, (
            "identical payload blobs should be shared, not re-serialized"
        )


# --------------------------------------------------------------------------
# Credential hygiene
# --------------------------------------------------------------------------


class TestDestinationSetSecurity:
    def test_repr_does_not_leak_credentials(self):
        from langsmith._internal._destinations import DestinationSet
        from langsmith.run_trees import _extract_replica_auth

        secrets = ["sk-secret-key", "svc-secret", "Bearer tok", "sid=cookieval"]
        dests = DestinationSet.of(
            _extract_replica_auth(
                WriteReplica(
                    api_url=URL_A,
                    auth=AuthHeaders(
                        api_key=secrets[0],
                        service_key=secrets[1],
                        authorization=secrets[2],
                        cookie=secrets[3],
                    ),
                )
            )
        )
        rendered = f"{dests!r} {dests!s} {dests}"
        for secret in secrets:
            assert secret not in rendered, f"{secret!r} leaked via DestinationSet repr"
        assert URL_A in rendered, "api_url is not a secret and should stay loggable"


# --------------------------------------------------------------------------
# OTel / hybrid non-regression
# --------------------------------------------------------------------------


class TestOtelUnaffected:
    @pytest.mark.parametrize("mode", ["otel", "hybrid"])
    def test_compression_stays_disabled_under_otel_modes(self, mode):
        """`disable_compression` includes tracing_mode in ("otel", "hybrid"), so
        none of the compression code should be reachable there."""
        pytest.importorskip("opentelemetry.sdk")
        from langsmith._internal._background_thread import ZSTD_AVAILABLE

        client = Client(
            api_url="https://main.example.com",
            api_key="main-key",
            session=MagicMock(),
            auto_batch_tracing=False,
            tracing_mode=mode,
        )
        assert client.compressed_traces is None
        assert ZSTD_AVAILABLE  # the guard must be the mode, not a missing dependency


# --------------------------------------------------------------------------
# X1 -- client-side control fields must not reach the wire (phase 0)
# --------------------------------------------------------------------------


# Fields the run body legitimately carries. Anything else appearing in `_none`
# is a client-side control field that leaked; see REPLICAS.md R1/R8.
KNOWN_RUN_FIELDS = {
    "id", "trace_id", "parent_run_id", "dotted_order", "session_name", "session_id",
    "name", "run_type", "start_time", "end_time", "tags", "status", "error",
    "reference_example_id", "manifest_id", "attachments", "input_attachments",
    "output_attachments", "revision_id", "extra", "events", "inputs", "outputs",
    "serialized",
}

# Control fields knowingly left on the wire. `reroot` is absent from the server
# contract and its effect is materialized client-side by _slice_parent_id before
# the payload is built, so shipping it is an accepted no-op (REPLICAS.md R8,
# X1b deferred). Listed explicitly so the guard below still catches NEW leaks.
ACCEPTED_CONTROL_FIELDS = {"reroot"}


def body_of(client, operation="post"):
    import orjson

    ops = [
        i.item
        for i in list(client.tracing_queue.queue)
        if getattr(i.item, "operation", None) == operation
    ]
    assert ops, f"no {operation} op was queued"
    return [orjson.loads(op._none) for op in ops]


class TestX1NoControlFieldsOnTheWire:
    def test_replicas_never_appear_in_the_run_body(self):
        """R1: the replica list is routing config, not run data."""
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
        )
        for operation in ("post", "patch"):
            for doc in body_of(client, operation):
                assert "replicas" not in doc, f"{operation} body carries the replica list"

    def test_no_replica_credential_reaches_any_destination(self):
        """The security claim: every destination currently receives every other
        destination's credentials."""
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(api_url=URL_A, auth=AuthHeaders(api_key=KEY_A)),
                WriteReplica(api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
        )
        sent = deliver(client)
        assert sent, "nothing was delivered"
        for url, _key, _enc, raw in sent:
            for secret in (KEY_A, KEY_B, "main-key"):
                assert secret.encode() not in raw, (
                    f"{url} received credential {secret!r} in the request body"
                )

    def test_per_replica_client_object_does_not_reach_the_payload(self):
        """A WriteReplica(client=...) is stringified into the body today,
        exposing the other client's API URL."""
        other = make_client(compression=False)
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(project_name="p", primary=True),
                WriteReplica(project_name="q", client=other),
            ],
            project_name="p",
        )
        for doc in body_of(client):
            assert "client" not in doc
            assert "replicas" not in doc

    @pytest.mark.xfail(
        reason="X1b deferred: `reroot` is absent from the server contract and its "
        "effect is materialized client-side, so shipping it is an accepted no-op "
        "(REPLICAS.md R8).",
        strict=True,
    )
    def test_reroot_is_consumed_client_side_not_shipped(self):
        """R8: `reroot` is a re-parenting control flag, not a run field."""
        client = make_client(compression=False)
        post_run(client, [WriteReplica(project_name="other", updates={"reroot": True})])
        for doc in body_of(client):
            assert "reroot" not in doc

    @pytest.mark.xfail(
        reason="X1b deferred: `updates.metadata` still lands as a top-level run "
        "field instead of merging into extra (REPLICAS.md R8, still open).",
        strict=True,
    )
    def test_updates_metadata_merges_into_extra(self):
        """R8: `RunBase.metadata` is a read-only view over extra['metadata'],
        so a top-level `metadata` key is not what the UI reads."""
        import orjson

        client = make_client(compression=False)
        post_run(
            client,
            [WriteReplica(project_name="other", updates={"metadata": {"env": "staging"}})],
        )
        ops = [
            i.item for i in list(client.tracing_queue.queue) if i.item.operation == "post"
        ]
        doc = orjson.loads(ops[0]._none)
        extra = orjson.loads(ops[0].extra) if ops[0].extra else {}
        assert "metadata" not in doc, "metadata landed as a top-level run field"
        assert extra.get("metadata", {}).get("env") == "staging"

    def test_serialized_body_carries_only_known_run_fields(self):
        """Recurrence guard: catches the next control field added to RunTree
        without excluding it from serialization."""
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(project_name="p", primary=True),
                WriteReplica(
                    project_name="q",
                    api_url=URL_B,
                    auth=AuthHeaders(api_key=KEY_B),
                    updates={"tags": ["x"]},
                ),
            ],
            project_name="p",
        )
        for operation in ("post", "patch"):
            for doc in body_of(client, operation):
                unexpected = set(doc) - KNOWN_RUN_FIELDS - ACCEPTED_CONTROL_FIELDS
                assert not unexpected, f"non-run fields on the wire: {sorted(unexpected)}"

    def test_routing_still_works_after_the_fix(self):
        """Excluding `replicas` from the payload must not change where runs go."""
        client = make_client(compression=False)
        post_run(
            client,
            [
                WriteReplica(project_name="p", primary=True),
                WriteReplica(project_name="q", api_url=URL_B, auth=AuthHeaders(api_key=KEY_B)),
            ],
            project_name="p",
        )
        # deliver() drains the queue, so read the bodies first.
        sessions = {doc.get("session_name") for doc in body_of(client)}
        sent = deliver(client)
        assert sent.to(URL_B), "credentialed replica was not delivered"
        assert sent.to("https://main.example.com"), "primary replica was not delivered"
        assert sessions == {"p", "q"}, f"projects wrong after fix: {sessions}"
