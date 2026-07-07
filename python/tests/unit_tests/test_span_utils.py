"""Unit tests for ``langsmith._internal.otel._span_utils``."""

from opentelemetry.sdk.trace import Event, ReadableSpan

from langsmith._internal.otel._span_utils import rebuild_readable_span


def _span() -> ReadableSpan:
    return ReadableSpan(
        name="orig",
        attributes={"a": 1},
        events=[Event(name="e0")],
        kind=None,
        start_time=1,
        end_time=2,
    )


def test_rebuild_overrides_attributes_and_events():
    span = _span()
    rebuilt = rebuild_readable_span(
        span, attributes={"b": 2}, events=[Event(name="e1")]
    )

    # Overridden fields.
    assert dict(rebuilt.attributes) == {"b": 2}
    assert [e.name for e in rebuilt.events] == ["e1"]
    # Copied-through fields.
    assert rebuilt.name == "orig"
    assert rebuilt.start_time == 1
    assert rebuilt.end_time == 2
    # The original span is never mutated.
    assert dict(span.attributes) == {"a": 1}
    assert [e.name for e in span.events] == ["e0"]


def test_rebuild_defaults_events_to_original():
    span = _span()
    rebuilt = rebuild_readable_span(span, attributes={"b": 2})
    assert [e.name for e in rebuilt.events] == ["e0"]
