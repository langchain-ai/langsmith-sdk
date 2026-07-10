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
from typing import Any, Optional

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from . import thread_id_from_context
from .translated_span import TranslatedSpan

__all__ = ["BaseLangSmithSpanProcessor", "TranslatedSpan"]

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

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        thread_id = thread_id_from_context()
        if thread_id:
            self._remember_thread_id(span.context.trace_id, str(thread_id))
        self.downstream.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        tspan = TranslatedSpan.of(span)

        export = True
        try:
            self._stamp_static_metadata(tspan)
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

        Returns True if ``on_end`` should export the span, or False to take
        ownership of the export.
        """
        raise NotImplementedError

    def _export(self, tspan: TranslatedSpan) -> None:
        """Forward the translated span downstream.

        Builds a fresh ``ReadableSpan`` from the draft (rewritten attributes/
        events) rather than mutating the original.
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

    def _stamp_static_metadata(self, tspan: TranslatedSpan) -> None:
        """Stamp the processor's static ``langsmith.metadata.*`` (never clobbering)."""
        for key, value in self._static_metadata.items():
            attr = f"langsmith.metadata.{key}"
            if value is not None and attr not in tspan.attributes:
                tspan.attributes[attr] = value

    def _stamp_thread_id(self, tspan: TranslatedSpan) -> None:
        """Stamp ``langsmith.metadata.thread_id`` from the id captured at ``on_start``.

        Reads the per-trace id captured at :meth:`on_start` — so spans that end in
        a detached task (where the ``ContextVar`` is unset) still get it. Leaves
        any id already on the span untouched, and skips when none was set.
        """
        if "langsmith.metadata.thread_id" in tspan.attributes:
            return
        thread_id = self._thread_id_by_trace.get(tspan.span.context.trace_id)
        if thread_id:
            tspan.set_thread_id(thread_id)

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
