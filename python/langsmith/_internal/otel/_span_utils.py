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
    name: str,
    end_time: Optional[int],
    events: Optional[list[Event]] = None,
) -> ReadableSpan:
    """Return a copy of ``span`` built from the given fields.

    Uses the caller-supplied ``name``, ``end_time``, and ``attributes`` (and
    ``events``), copying every other field from ``span`` unchanged. The caller
    passes ``name`` and ``end_time`` directly (typically the source span's own
    values, or a rewritten name/end for a renamed or merged span). ``events``
    defaults to the original span's events when not overridden. The original span
    is never mutated.
    """
    return ReadableSpan(
        name=name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=events if events is not None else (span.events or []),
        links=span.links,
        kind=span.kind,
        status=span.status,
        start_time=span.start_time,
        end_time=end_time,
        instrumentation_scope=span.instrumentation_scope,
    )
