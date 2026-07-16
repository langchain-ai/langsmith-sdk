"""``TranslatedSpan`` — the mutable draft handlers rewrite before export.

Split out of :mod:`langsmith._internal.voice.base_span_processor` so the base
processor stays focused on span lifecycle and export wiring. The framework
subclasses (Pipecat, LiveKit) rewrite one of these per span while translating
``lk.*`` / ``pipecat.*`` data into LangSmith's ``gen_ai.*`` / ``langsmith.*``
namespaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from opentelemetry.sdk.trace import Event, ReadableSpan

from langsmith._internal.otel._span_utils import rebuild_readable_span


def _clean_token_details(details: Optional[dict[str, Any]]) -> dict[str, int]:
    """Keep only the int-valued detail keys, dropping ``None`` / non-numeric."""
    if not details:
        return {}
    return {k: int(v) for k, v in details.items() if isinstance(v, (int, float))}


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
    name: str
    end_time: Optional[int]

    @classmethod
    def of(cls, span: ReadableSpan) -> TranslatedSpan:
        """Seed a draft from a span's own (read-only) fields, attributes, and events."""
        return cls(
            span,
            dict(span.attributes or {}),
            list(span.events or []),
            span.name,
            span.end_time,
        )

    def finalize(self) -> ReadableSpan:
        """Build the export span: the original's fields + our rewritten ones."""
        return rebuild_readable_span(
            self.span,
            attributes=self.attributes,
            events=self.events,
            name=self.name,
            end_time=self.end_time,
        )

    def set_name(self, name: str) -> None:
        """Set the exported span's name (the LangSmith run name)."""
        self.name = name

    def set_end_time(self, end_time_ns: int) -> None:
        """Set the exported span's end time (epoch ns).

        Lets a span merged from two sources report a duration that runs past its
        own end — e.g. a tool span spanning from the call to the result.
        """
        self.end_time = end_time_ns

    def set_kind(self, kind: str) -> None:
        """Set ``langsmith.span.kind`` (``llm`` / ``chain`` / ``tool`` / …)."""
        self.attributes["langsmith.span.kind"] = kind

    def set_thread_id(self, thread_id: str) -> None:
        """Set ``langsmith.metadata.thread_id`` (the conversation/thread id)."""
        self.attributes["langsmith.metadata.thread_id"] = thread_id

    def set_provider(self, provider: Optional[str]) -> None:
        """Set ``provider`` on both gen_ai.* provider keys (no-op if empty).

        LangSmith maps either ``gen_ai.provider.name`` (newer) or the legacy
        ``gen_ai.system`` to ``ls_provider``; writing both is version-agnostic.
        The caller passes an already-resolved slug — normalization is the
        integration's concern.
        """
        if provider:
            self.attributes["gen_ai.provider.name"] = provider
            self.attributes["gen_ai.system"] = provider

    def set_model(self, model: Optional[str]) -> None:
        """Set the request model on ``gen_ai.request.model`` and its metadata mirror."""
        if model:
            self.attributes["gen_ai.request.model"] = str(model)
            self.attributes["langsmith.metadata.model_name"] = str(model)

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

    def set_usage(
        self,
        *,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        input_token_details: Optional[dict[str, int]] = None,
        output_token_details: Optional[dict[str, int]] = None,
    ) -> None:
        """Write the given token usage as ``langsmith.usage_metadata`` (JSON).

        Callers pass the complete usage — it replaces the flat ``gen_ai.usage.*``
        at ingest. No-op when nothing is given.
        """
        usage: dict[str, Any] = {}
        if input_tokens is not None:
            usage["input_tokens"] = int(input_tokens)
        if output_tokens is not None:
            usage["output_tokens"] = int(output_tokens)
        if total_tokens is not None:
            usage["total_tokens"] = int(total_tokens)
        if details := _clean_token_details(input_token_details):
            usage["input_token_details"] = details
        if details := _clean_token_details(output_token_details):
            usage["output_token_details"] = details
        if usage:
            self.attributes["langsmith.usage_metadata"] = json.dumps(usage)

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

    def set_tool_input(self, tool_input: Any) -> None:
        """Write a tool run's input to ``gen_ai.prompt`` as raw I/O (not messages).

        A ``str`` is passed through unchanged; any other value is JSON-encoded.
        """
        self.attributes["gen_ai.prompt"] = (
            tool_input if isinstance(tool_input, str) else json.dumps(tool_input)
        )

    def set_tool_output(self, tool_output: Any) -> None:
        """Write a tool run's output to ``gen_ai.completion`` as raw I/O (not messages).

        A ``str`` is passed through unchanged; any other value is JSON-encoded.
        """
        self.attributes["gen_ai.completion"] = (
            tool_output if isinstance(tool_output, str) else json.dumps(tool_output)
        )
