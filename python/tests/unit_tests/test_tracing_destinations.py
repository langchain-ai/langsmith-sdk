"""Per-run tracing destination override via ``langsmith_extra``.

The feature under test is deliberately narrow: setting
``langsmith_extra={"tracing_destinations": "langsmith" | "otel" | "hybrid"}``
on a ``@traceable`` call routes that run (and any descendants created via
``RunTree.create_child``) to the requested destination. No client-level
default, no env var changes, no decorator kwarg.
"""

from __future__ import annotations

import logging
import uuid
from queue import Queue
from typing import Iterator
from unittest import mock

import pytest

from langsmith import Client, run_helpers, run_trees
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _dispatch_batch,
)
from langsmith._internal._operations import SerializedRunOperation
from langsmith.utils import get_env_var


@pytest.fixture(autouse=True)
def _clear_env_cache() -> Iterator[None]:
    """Neutralise :func:`langsmith.utils.get_env_var`'s lru_cache between tests."""
    get_env_var.cache_clear()
    yield
    get_env_var.cache_clear()


# ---------------------------------------------------------------------------
# RunTree field + propagation
# ---------------------------------------------------------------------------


class TestRunTreeField:
    def test_field_excluded_from_serialization(self) -> None:
        run = run_trees.RunTree(name="r", inputs={}, tracing_destinations="otel")
        assert "tracing_destinations" not in run.model_dump()
        assert "tracing_destinations" not in run.model_dump(exclude_none=True)

    def test_legacy_default_is_none(self) -> None:
        assert run_trees.RunTree(name="r", inputs={}).tracing_destinations is None

    def test_create_child_inherits(self) -> None:
        parent = run_trees.RunTree(name="p", inputs={}, tracing_destinations="hybrid")
        assert parent.create_child(name="c").tracing_destinations == "hybrid"

    def test_create_child_inherits_none(self) -> None:
        parent = run_trees.RunTree(name="p", inputs={})
        assert parent.create_child(name="c").tracing_destinations is None


# ---------------------------------------------------------------------------
# Client._resolve_tracing_destination
# ---------------------------------------------------------------------------


def _make_client() -> Client:
    return Client(
        api_url="http://localhost:1984",
        api_key="test",
        auto_batch_tracing=False,
    )


class TestResolveTracingDestination:
    def test_none_passes_through(self) -> None:
        assert _make_client()._resolve_tracing_destination(None) is None

    def test_langsmith_never_needs_otel(self) -> None:
        # No exporter; "langsmith" is always fine.
        client = _make_client()
        assert client.otel_exporter is None
        assert client._resolve_tracing_destination("langsmith") == "langsmith"

    def test_bogus_value_raises_synchronously(self) -> None:
        # Typos must be caught at the caller, not later on the bg thread.
        client = _make_client()
        with pytest.raises(ValueError, match="Invalid tracing_destinations"):
            client._resolve_tracing_destination("OTEL")

    def test_otel_without_exporter_warns_once_and_downgrades(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = _make_client()
        assert client.otel_exporter is None
        caplog.set_level(logging.WARNING, logger="langsmith.client")

        for _ in range(4):
            assert client._resolve_tracing_destination("otel") is None
            assert client._resolve_tracing_destination("hybrid") is None

        downgrade_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and "no OpenTelemetry exporter" in r.getMessage()
        ]
        assert len(downgrade_records) == 1

    def test_with_exporter_returns_value(self) -> None:
        client = _make_client()
        client.otel_exporter = mock.Mock()
        assert client._resolve_tracing_destination("otel") == "otel"
        assert client._resolve_tracing_destination("hybrid") == "hybrid"


# ---------------------------------------------------------------------------
# Dispatcher: per-item destination partitioning
# ---------------------------------------------------------------------------


def _make_queue_item(destination: object = None) -> TracingQueueItem:
    op = SerializedRunOperation(
        operation="post",
        id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        _none=b"{}",
        inputs=None,
        outputs=None,
        events=None,
        attachments=None,
    )
    return TracingQueueItem(priority="0", item=op, destination=destination)


class TestDispatchBatch:
    def test_fast_path_when_no_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No item carries a destination → single-handler call, matching
        today's behaviour exactly."""
        monkeypatch.delenv("LANGSMITH_OTEL_ENABLED", raising=False)
        monkeypatch.delenv("LANGCHAIN_OTEL_ENABLED", raising=False)
        client = _make_client()
        batch = [_make_queue_item(), _make_queue_item()]
        queue: Queue = Queue()

        with (
            mock.patch(
                "langsmith._internal._background_thread._tracing_thread_handle_batch"
            ) as ls_h,
            mock.patch(
                "langsmith._internal._background_thread._otel_tracing_thread_handle_batch"
            ) as otel_h,
            mock.patch(
                "langsmith._internal._background_thread._hybrid_tracing_thread_handle_batch"
            ) as hybrid_h,
        ):
            _dispatch_batch(client, queue, batch, use_multipart=True)

        ls_h.assert_called_once()
        otel_h.assert_not_called()
        hybrid_h.assert_not_called()
        # Exactly today's shape: one call with the full batch.
        assert list(ls_h.call_args.args[2]) == batch

    def test_fast_path_respects_global_hybrid_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LANGSMITH_OTEL_ENABLED", "true")
        monkeypatch.delenv("LANGSMITH_OTEL_ONLY", raising=False)
        monkeypatch.delenv("LANGCHAIN_OTEL_ONLY", raising=False)
        get_env_var.cache_clear()
        client = _make_client()
        batch = [_make_queue_item()]
        queue: Queue = Queue()

        with (
            mock.patch(
                "langsmith._internal._background_thread._tracing_thread_handle_batch"
            ) as ls_h,
            mock.patch(
                "langsmith._internal._background_thread._otel_tracing_thread_handle_batch"
            ) as otel_h,
            mock.patch(
                "langsmith._internal._background_thread._hybrid_tracing_thread_handle_batch"
            ) as hybrid_h,
        ):
            _dispatch_batch(client, queue, batch, use_multipart=True)

        ls_h.assert_not_called()
        otel_h.assert_not_called()
        hybrid_h.assert_called_once()

    def test_mixed_batch_is_partitioned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LANGSMITH_OTEL_ENABLED", raising=False)
        client = _make_client()
        items = [
            _make_queue_item("langsmith"),
            _make_queue_item("otel"),
            _make_queue_item("hybrid"),
            _make_queue_item("langsmith"),
            _make_queue_item(None),  # falls back to default → "langsmith"
        ]
        queue: Queue = Queue()

        with (
            mock.patch(
                "langsmith._internal._background_thread._tracing_thread_handle_batch"
            ) as ls_h,
            mock.patch(
                "langsmith._internal._background_thread._otel_tracing_thread_handle_batch"
            ) as otel_h,
            mock.patch(
                "langsmith._internal._background_thread._hybrid_tracing_thread_handle_batch"
            ) as hybrid_h,
        ):
            _dispatch_batch(client, queue, items, use_multipart=True)

        ls_h.assert_called_once()
        otel_h.assert_called_once()
        hybrid_h.assert_called_once()
        assert len(ls_h.call_args.args[2]) == 3
        assert len(otel_h.call_args.args[2]) == 1
        assert len(hybrid_h.call_args.args[2]) == 1

    def test_unknown_destination_routes_to_langsmith(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Defence-in-depth: a queue item with an unrecognised destination
        must not crash the background thread."""
        monkeypatch.delenv("LANGSMITH_OTEL_ENABLED", raising=False)
        client = _make_client()
        items = [_make_queue_item("garbage")]
        queue: Queue = Queue()

        with (
            mock.patch(
                "langsmith._internal._background_thread._tracing_thread_handle_batch"
            ) as ls_h,
            mock.patch(
                "langsmith._internal._background_thread._otel_tracing_thread_handle_batch"
            ) as otel_h,
        ):
            _dispatch_batch(client, queue, items, use_multipart=True)

        ls_h.assert_called_once()
        otel_h.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-end: @traceable + langsmith_extra → TracingQueueItem.destination
# ---------------------------------------------------------------------------


def _patched_client(monkeypatch: pytest.MonkeyPatch, seen: list) -> Client:
    """Return a Client whose ``create_run`` records ``tracing_destinations``.

    Patches at the *class* level to satisfy ``__slots__``.
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    client = _make_client()
    client.otel_exporter = mock.Mock()

    def _record(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(kwargs.get("tracing_destinations"))

    def _noop(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        pass

    monkeypatch.setattr(Client, "create_run", _record)
    monkeypatch.setattr(Client, "update_run", _noop)
    return client


class TestTraceableIntegration:
    def test_langsmith_extra_sets_destination_on_outgoing_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list = []
        client = _patched_client(monkeypatch, seen)

        @run_helpers.traceable(client=client)
        def f() -> int:
            return 1

        f(langsmith_extra={"tracing_destinations": "otel"})
        assert seen == ["otel"]

    def test_override_propagates_to_child_runs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list = []
        client = _patched_client(monkeypatch, seen)

        @run_helpers.traceable(client=client)
        def inner() -> int:
            return 2

        @run_helpers.traceable(client=client)
        def outer() -> int:
            return inner()

        outer(langsmith_extra={"tracing_destinations": "hybrid"})
        assert seen == ["hybrid", "hybrid"]

    def test_sibling_traces_do_not_share_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An override on one top-level trace must not leak to a sibling."""
        seen: list = []
        client = _patched_client(monkeypatch, seen)

        @run_helpers.traceable(client=client)
        def a() -> int:
            return 1

        @run_helpers.traceable(client=client)
        def b() -> int:
            return 2

        a(langsmith_extra={"tracing_destinations": "otel"})
        b()
        assert seen == ["otel", None]

    def test_no_override_leaves_destination_as_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list = []
        client = _patched_client(monkeypatch, seen)

        @run_helpers.traceable(client=client)
        def f() -> int:
            return 1

        f()
        assert seen == [None]
