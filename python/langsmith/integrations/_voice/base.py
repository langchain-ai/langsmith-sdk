"""``BaseLangSmithSpanProcessor`` — Track A's shared OTel span processor.

The framework integrations that emit their own OpenTelemetry spans (Pipecat,
LiveKit) translate those spans into the ``gen_ai.*`` / ``langsmith.*`` attribute
namespaces LangSmith's OTLP ingester understands, then forward them to an
exporter. This base owns everything that translation shares — the downstream
wrapping, the LangSmith OTLP exporter default, opt-in ``thread_id`` injection,
the ``gen_ai.*`` message writers, OpenAI→LangChain message normalization, and
size-capped audio attachment — so each framework subclass implements only
``_dispatch`` (classify a span by name, rewrite it, export it).

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
from typing import Any, Callable, Optional

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Default audio attachment cap (bytes) before base64 — guards against a long
# call producing a multi-megabyte span attribute.
DEFAULT_AUDIO_SIZE_LIMIT = 20_000_000


class BaseLangSmithSpanProcessor(SpanProcessor):
    """Shared base for the OTel→LangSmith framework span processors.

    Subclasses implement :meth:`_dispatch` to classify each ended span, rewrite
    its attributes via the helpers here, and call :meth:`_export`. The base
    handles the downstream/exporter wiring, ``thread_id`` injection, and static
    metadata stamping.
    """

    def __init__(
        self,
        downstream_processor: Optional[SpanProcessor] = None,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
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
            thread_id_provider: opt-in conversation id for LangSmith thread
                grouping; called per span, ``None`` disables.
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
        self.thread_id_provider = thread_id_provider
        self.audio_size_limit_bytes = audio_size_limit_bytes
        self._static_metadata = metadata or {}

    # -- span lifecycle -------------------------------------------------------

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        for key, value in self._static_metadata.items():
            if value is not None:
                span.set_attribute(f"langsmith.metadata.{key}", value)
        self.downstream.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        self._inject_thread_id(span)
        self._dispatch(span)

    def _dispatch(self, span: ReadableSpan) -> None:
        """Classify the span, rewrite its attributes, and export it.

        Subclasses MUST implement this and call :meth:`_export` for each span
        they want exported (or defer it). The default raises.
        """
        raise NotImplementedError

    def _export(self, span: ReadableSpan) -> None:
        """Forward a (rewritten) span to the downstream processor."""
        self._pre_export(span)
        self.downstream.on_end(span)

    def _pre_export(self, span: ReadableSpan) -> None:
        """Run just before export (e.g. a blanket vendor-attribute pass-through)."""

    def shutdown(self) -> None:
        self.downstream.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.downstream.force_flush(timeout_millis)

    # -- shared helpers -------------------------------------------------------

    def _inject_thread_id(self, span: ReadableSpan) -> None:
        """Stamp ``langsmith.metadata.thread_id`` from the provider (opt-in).

        LangSmith needs the thread id on every run for thread-level filtering and
        token/cost aggregation. Never clobbers an id set upstream.
        """
        if (
            self.thread_id_provider is not None
            and "langsmith.metadata.thread_id" not in span.attributes
        ):
            thread_id = self.thread_id_provider()
            if thread_id:
                span._attributes["langsmith.metadata.thread_id"] = str(thread_id)

    @staticmethod
    def _set_kind(span: ReadableSpan, kind: str) -> None:
        span._attributes["langsmith.span.kind"] = kind

    @staticmethod
    def _exclude_from_message_view(span: ReadableSpan) -> None:
        """Drop a span from the conversation Messages view (still in the tree).

        That view reconstructs the chat from ``llm``/``tool`` runs. STT/TTS spans
        are tagged ``llm``-kind for the tree but would inject fake turns (raw
        transcripts, "Generated audio for: …"), so they opt out here.
        """
        span._attributes["langsmith.metadata.ls_message_view_exclude"] = True

    @staticmethod
    def _set_messages(
        span: ReadableSpan,
        *,
        prompt: Optional[list[dict]] = None,
        completion: Optional[list[dict]] = None,
    ) -> None:
        """Write simple role/content turns in the indexed + singular forms.

        For plain conversation turns (STT, TTS, an exchange) where messages have
        only role + content. Writes the indexed ``gen_ai.prompt.{n}.role/content``
        attributes and the singular ``gen_ai.prompt`` JSON list. For messages
        that carry structured fields (tool calls), use :meth:`_set_messages_json`
        instead — the indexed form can't represent them.
        """
        if prompt is not None:
            for i, msg in enumerate(prompt):
                span._attributes[f"gen_ai.prompt.{i}.role"] = msg.get("role", "user")
                span._attributes[f"gen_ai.prompt.{i}.content"] = str(
                    msg.get("content", "")
                )
            span._attributes["gen_ai.prompt"] = json.dumps(prompt)
        if completion is not None:
            for i, msg in enumerate(completion):
                span._attributes[f"gen_ai.completion.{i}.role"] = msg.get(
                    "role", "assistant"
                )
                span._attributes[f"gen_ai.completion.{i}.content"] = str(
                    msg.get("content", "")
                )
            span._attributes["gen_ai.completion"] = json.dumps(completion)

    @staticmethod
    def _set_messages_json(
        span: ReadableSpan,
        *,
        prompt: Optional[list[dict]] = None,
        completion: Optional[list[dict]] = None,
    ) -> None:
        """Write messages in the singular ``{"messages": [...]}`` JSON form only.

        This is the form for LLM calls and the conversation root: it can carry
        structured ``tool_calls`` / ``tool_call_id`` that the indexed
        ``gen_ai.prompt.{n}.*`` attributes can't, and it takes precedence at
        ingest — so the indexed form is deliberately *not* written here (it would
        win and drop the tool calls).
        """
        if prompt is not None:
            span._attributes["gen_ai.prompt"] = json.dumps({"messages": prompt})
        if completion is not None:
            span._attributes["gen_ai.completion"] = json.dumps({"messages": completion})

    @staticmethod
    def _flatten_tool_call(raw_call: Any) -> Optional[dict]:
        """Normalize one OpenAI-shape tool call to LangChain's flat shape.

        OpenAI:  ``{"id", "type": "function", "function": {"name", "arguments"}}``
        (``arguments`` a JSON string). LangChain:
        ``{"type": "tool_call", "id", "name", "args"}`` with ``args`` an object —
        which is what LangSmith renders as a tool-call block.
        """
        if isinstance(raw_call, str):
            try:
                raw_call = json.loads(raw_call)
            except json.JSONDecodeError:
                return None
        if not isinstance(raw_call, dict):
            return None
        fn = raw_call.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                pass
        return {
            "type": "tool_call",
            "id": raw_call.get("id"),
            "name": fn.get("name"),
            "args": args if isinstance(args, dict) else {},
        }

    @classmethod
    def _to_langchain_message(cls, msg: dict) -> dict:
        """Convert one OpenAI-format context message to LangChain flat format.

        Flattens assistant ``tool_calls`` (see :meth:`_flatten_tool_call`) and
        carries ``tool_call_id`` / ``name`` for tool-result messages so LangSmith
        links them back to the call.
        """
        content = msg.get("content")
        if not isinstance(content, str):
            content = "" if content is None else json.dumps(content)
        out: dict = {"role": str(msg.get("role", "")), "content": content}
        tool_calls = [
            tc
            for raw in (msg.get("tool_calls") or [])
            if (tc := cls._flatten_tool_call(raw)) is not None
        ]
        if tool_calls:
            out["tool_calls"] = tool_calls
        if msg.get("tool_call_id"):
            out["tool_call_id"] = str(msg["tool_call_id"])
        if msg.get("role") == "tool" and msg.get("name"):
            out["name"] = str(msg["name"])
        return out

    def _attach_audio(
        self, span: ReadableSpan, *, name: str, data: bytes, mime_type: str
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
        span._attributes["langsmith.attachments"] = json.dumps(
            [
                {
                    "name": name,
                    "content": base64.b64encode(data).decode("ascii"),
                    "mime_type": mime_type,
                }
            ]
        )
        return True
