"""Shared OpenTelemetry span helpers for the LangSmith OTel integrations.

The framework integrations rewrite spans before export but must not mutate the
original ``ReadableSpan`` (its attributes/events are meant to be read-only). The
supported workaround is to build a *new* ``ReadableSpan`` carrying the original's
fields with the rewritten attributes/events substituted. ``ReadableSpan``'s
constructor is not part of OpenTelemetry's public API, so this helper isolates
that one call site for every integration that needs it (voice, Strands).
"""

from __future__ import annotations

from typing import Optional

from opentelemetry.sdk.trace import Event, ReadableSpan


def rebuild_readable_span(
    span: ReadableSpan,
    *,
    attributes: dict,
    events: Optional[list[Event]] = None,
    name: Optional[str] = None,
    end_time: Optional[int] = None,
) -> ReadableSpan:
    """Return a copy of ``span`` with rewritten ``attributes`` (and ``events``).

    Copies every other field from ``span`` unchanged. ``events`` defaults to the
    original span's events when not overridden. ``name`` / ``end_time`` override
    the source span's values when given (e.g. to rename a span to its tool name
    or extend a merged span's end past its own). The original span is never
    mutated.
    """
    return ReadableSpan(
        name=name if name is not None else span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=events if events is not None else (span.events or []),
        links=span.links,
        kind=span.kind,
        status=span.status,
        start_time=span.start_time,
        end_time=end_time if end_time is not None else span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )
