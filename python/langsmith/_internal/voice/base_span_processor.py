"""``BaseLangSmithSpanProcessor`` — Track A's shared OTel span processor.

The framework integrations that emit their own OpenTelemetry spans (Pipecat,
LiveKit) translate those spans into the ``gen_ai.*`` / ``langsmith.*`` attribute
namespaces LangSmith's OTLP ingester understands, then forward them to an
exporter. This base owns everything that translation shares — the downstream
wrapping, the LangSmith OTLP exporter default, opt-in ``thread_id`` stamping,
the ``gen_ai.*`` message writers, and size-capped audio attachment — so each
framework subclass implements only
``_dispatch`` (classify a span by name and rewrite it); the base exports it.

The processor wraps a *downstream* processor rather than being added as a
sibling: ``on_end`` rewrites attributes and then forwards to the downstream, so
spans are always translated before export. The default downstream is a
``BatchSpanProcessor`` around the LangSmith ``OtelExporter`` (see
:mod:`langsmith.integrations.otel`), which targets LangSmith's
``/otel/v1/traces`` endpoint with the right auth headers from standard LangSmith
config — no OTLP env vars required.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from opentelemetry.sdk.trace import Event, ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from langsmith._internal.otel._span_utils import rebuild_readable_span

from . import thread_id_from_context

logger = logging.getLogger(__name__)

# Default cap (bytes) on raw audio before base64 encoding. The LangSmith
# ingester accepts attachments up to ~200MB; base64 inflates by ~1.33x, so a
# 150MB raw cap encodes to ~200MB — right at that ceiling. Override per
# processor via ``audio_size_limit_bytes`` (or ``None`` to disable the cap).
DEFAULT_AUDIO_SIZE_LIMIT = 150_000_000

# Hard ceiling on the per-trace thread-id cache (see ``_remember_thread_id``).
# Entries are tiny strings and are normally freed at conversation end via
# ``_forget_thread_id``; this bounds memory for conversations that never reach
# cleanup (crash, dropped connection), evicting oldest-first.
_THREAD_ID_CACHE_MAXSIZE = 100_000


@dataclass
class TranslatedSpan:
    """A span being translated into LangSmith's namespaces before export.

    Wraps the original read-only OTel ``ReadableSpan`` with mutable
    ``attributes`` and ``events`` seeded from it. Handlers rewrite the copies
    while translating; :meth:`finalize` builds a fresh ``ReadableSpan`` from them
    — so OpenTelemetry's private ``span._attributes`` / ``span._events`` are
    never mutated.

    Created per span in :meth:`BaseLangSmithSpanProcessor.on_end` and threaded
    through dispatch — no global state. A processor that defers a span (see
    :meth:`BaseLangSmithSpanProcessor._dispatch`) simply holds the
    ``TranslatedSpan`` itself until it exports it later, so the in-progress
    translation outlives the originating ``on_end`` call.
    """

    span: ReadableSpan
    attributes: dict[str, Any]
    events: list[Event]

    @classmethod
    def of(cls, span: ReadableSpan) -> TranslatedSpan:
        """Seed a draft from a span's own (read-only) attributes and events."""
        return cls(span, dict(span.attributes or {}), list(span.events or []))

    def finalize(self) -> ReadableSpan:
        """Build the export span: the original's fields + our rewritten attrs/events."""
        return rebuild_readable_span(
            self.span, attributes=self.attributes, events=self.events
        )

    def set_kind(self, kind: str) -> None:
        """Set ``langsmith.span.kind`` (``llm`` / ``chain`` / ``tool`` / …)."""
        self.attributes["langsmith.span.kind"] = kind

    def set_thread_id(self, thread_id: str) -> None:
        """Set ``langsmith.metadata.thread_id`` (the conversation/thread id)."""
        self.attributes["langsmith.metadata.thread_id"] = thread_id

    def exclude_from_message_view(self) -> None:
        """Drop this span from the conversation Messages view (still in the tree).

        That view reconstructs the chat from ``llm``/``tool`` runs. STT/TTS spans
        are tagged ``llm``-kind for the tree but would otherwise add fake turns
        (raw transcripts, "Generated audio for: …"), so they opt out here.
        """
        self.attributes["langsmith.metadata.ls_message_view_exclude"] = True

    def set_root_span(self, is_root: bool) -> None:
        """Mark the span as the trace root (``langsmith.root_span``)."""
        self.attributes["langsmith.root_span"] = is_root

    def set_metadata(self, key: str, value: Any) -> None:
        """Set ``langsmith.metadata.<key>`` to the given value.

        LangSmith surfaces everything under ``langsmith.metadata.*`` as run
        metadata. Note ``langsmith.root_span`` and ``langsmith.span.kind`` are NOT
        metadata — they live in the top-level ``langsmith.*`` namespace and have
        their own setters / direct writes.
        """
        self.attributes[f"langsmith.metadata.{key}"] = value

    def set_messages(
        self,
        *,
        prompt: Optional[list[dict]] = None,
        completion: Optional[list[dict]] = None,
    ) -> None:
        """Write ``gen_ai.prompt``/``gen_ai.completion`` as ``{"messages": [...]}``."""
        if prompt is not None:
            self.attributes["gen_ai.prompt"] = json.dumps({"messages": prompt})
        if completion is not None:
            self.attributes["gen_ai.completion"] = json.dumps({"messages": completion})


class BaseLangSmithSpanProcessor(SpanProcessor):
    """Shared base for the OTel→LangSmith framework span processors.

    Subclasses implement :meth:`_dispatch` to classify each ended span and
    rewrite its attributes via the helpers here; the base exports it. The base
    handles the downstream/exporter wiring, ``thread_id`` stamping, and static
    metadata stamping.
    """

    def __init__(
        self,
        downstream_processor: Optional[SpanProcessor] = None,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Create the processor.

        Args:
            downstream_processor: where rewritten spans are forwarded. Defaults
                to ``BatchSpanProcessor(OtelExporter(...))`` targeting LangSmith.
            api_key: LangSmith API key for the default exporter. Defaults to
                ``LANGSMITH_API_KEY``.
            project: LangSmith project for the default exporter. Defaults to
                ``LANGSMITH_PROJECT``.
            endpoint: full OTLP traces URL for the default exporter. Defaults to
                ``{LANGSMITH_ENDPOINT}/otel/v1/traces``.
            audio_size_limit_bytes: skip attaching audio larger than this; set
                ``None`` to disable the cap.
            metadata: static ``langsmith.metadata.*`` stamped on every span.
        """
        super().__init__()
        if downstream_processor is None:
            from langsmith.integrations.otel.processor import OtelExporter

            downstream_processor = BatchSpanProcessor(
                OtelExporter(url=endpoint, api_key=api_key, project=project)
            )
        self.downstream = downstream_processor
        self.audio_size_limit_bytes = audio_size_limit_bytes
        self._static_metadata = metadata or {}
        # Per-trace thread id, captured at ``on_start`` (in the conversation's
        # task, where ``set_thread_id`` was called) and reused for every span in
        # the trace at export — so spans that END in a detached framework task,
        # where the ``set_thread_id`` ``ContextVar`` is invisible, still get it.
        # Keyed by int trace_id. Not thread-safe (like the subclass caches): the
        # voice frameworks drive on_start/on_end from a single asyncio loop.
        self._thread_id_by_trace: dict[int, str] = {}

    # -- span lifecycle -------------------------------------------------------

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        for key, value in self._static_metadata.items():
            if value is not None:
                span.set_attribute(f"langsmith.metadata.{key}", value)
        # Capture the thread id here, at the earliest in-context moment. on_start
        # runs synchronously in the task that starts the span; the conversation's
        # root span starts in the task where set_thread_id was called, so the
        # ContextVar is visible now even when later spans END in detached tasks
        # where it is not. _stamp_thread_id then recovers it per trace.
        thread_id = thread_id_from_context()
        context = getattr(span, "context", None)
        if thread_id and context is not None:
            self._remember_thread_id(context.trace_id, str(thread_id))
        self.downstream.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        # Isolate translation from export: a failure rewriting one span must
        # never drop it or propagate into the OTel provider's span-ending path
        # (which would disrupt other processors and the traced app). On error we
        # log and still export the span untranslated — degraded, not lost.
        #
        # _dispatch returns whether the base should export the span now. A
        # subclass that defers (returns False) owns its own later _export call;
        # any other return value — including a dispatch failure — leaves
        # export=True so the span is still forwarded exactly once.
        tspan = TranslatedSpan.of(span)
        export = True
        try:
            self._stamp_thread_id(tspan)
            export = self._dispatch(tspan) is not False
        except Exception:
            logger.warning(
                "langsmith voice: failed processing span %r; "
                "exporting it untranslated.",
                getattr(span, "name", "?"),
                exc_info=True,
            )
        if export:
            try:
                self._export(tspan)
            except Exception:
                logger.warning(
                    "langsmith voice: failed exporting span %r.",
                    getattr(span, "name", "?"),
                    exc_info=True,
                )

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        """Classify the span and rewrite its attributes on the draft.

        Returns whether :meth:`on_end` should export the span. Return ``True``
        (the common case) to have the base export it exactly once. Return
        ``False`` to take ownership of the export — e.g. to defer the span until
        a later event — in which case the subclass MUST hold ``tspan`` and call
        :meth:`_export` with it itself, exactly once. Subclasses that return
        ``True`` MUST NOT call :meth:`_export`. The default raises.
        """
        raise NotImplementedError

    def _export(self, tspan: TranslatedSpan) -> None:
        """Forward the translated span downstream.

        Builds a fresh ``ReadableSpan`` from the draft (rewritten attributes/
        events) rather than mutating the original — so we never poke
        OpenTelemetry's private span internals.
        """
        self._pre_export(tspan)
        self.downstream.on_end(tspan.finalize())

    def _pre_export(self, tspan: TranslatedSpan) -> None:
        """Run just before export (e.g. a blanket vendor-attribute pass-through)."""

    def shutdown(self) -> None:
        self.downstream.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.downstream.force_flush(timeout_millis)

    # -- shared helpers -------------------------------------------------------

    def _stamp_thread_id(self, tspan: TranslatedSpan) -> None:
        """Stamp ``langsmith.metadata.thread_id`` from the per-context id (opt-in).

        LangSmith needs the thread id on every run for thread-level filtering and
        token/cost aggregation. The id is set via
        :func:`~langsmith._internal.voice.set_thread_id`, a ``ContextVar``, so
        concurrent conversations each see their own value. Resolves it as:

        1. leave any id already on the span untouched (never clobber upstream);
        2. else the value captured for this trace at :meth:`on_start` — robust to
           spans that end in a detached task where the ``ContextVar`` is unset;
        3. else the ``ContextVar`` directly (this span IS in context and is the
           first we've seen for the trace), backfilling the cache for its peers.

        Stamping is skipped (``None``) when no id was ever set for the trace.
        """
        if "langsmith.metadata.thread_id" in tspan.attributes:
            return
        trace_id = tspan.span.context.trace_id
        thread_id = self._thread_id_by_trace.get(trace_id) or thread_id_from_context()
        if thread_id:
            thread_id = str(thread_id)
            tspan.set_thread_id(thread_id)
            self._remember_thread_id(trace_id, thread_id)

    def _remember_thread_id(self, trace_id: int, thread_id: str) -> None:
        """Cache a trace's thread id, evicting oldest-first when at capacity."""
        cache = self._thread_id_by_trace
        if trace_id not in cache and len(cache) >= _THREAD_ID_CACHE_MAXSIZE:
            cache.pop(next(iter(cache)), None)
        cache[trace_id] = thread_id

    def _forget_thread_id(self, trace_id: int) -> None:
        """Drop a trace's cached thread id (called from subclass cleanup)."""
        self._thread_id_by_trace.pop(trace_id, None)

    def _attach_audio(
        self, tspan: TranslatedSpan, *, name: str, data: bytes, mime_type: str
    ) -> bool:
        """Attach audio bytes to a span via ``langsmith.attachments`` (base64).

        Honors ``audio_size_limit_bytes`` (skips oversize audio). Returns whether
        the audio was attached. Uses the OTel attachment path documented at
        docs.langchain.com/langsmith/trace-with-opentelemetry.
        """
        if not data:
            return False
        if (
            self.audio_size_limit_bytes is not None
            and len(data) > self.audio_size_limit_bytes
        ):
            return False
        tspan.attributes["langsmith.attachments"] = json.dumps(
            [
                {
                    "name": name,
                    "content": base64.b64encode(data).decode("ascii"),
                    "mime_type": mime_type,
                }
            ]
        )
        return True
