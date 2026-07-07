"""Utilities for setting LangSmith OpenTelemetry attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from langsmith._internal import _orjson

if TYPE_CHECKING:
    from opentelemetry.trace import Span  # type: ignore[import]

LANGSMITH_METADATA_PREFIX = "langsmith.metadata"


def otel_safe_attribute_value(value: Any) -> Optional[Any]:
    """Convert a LangSmith metadata value for safe use in application OTel spans."""
    if value is None:
        return None
    if isinstance(value, (bool, bytes, int, float, str)):
        return value
    if isinstance(value, (dict, list)):
        try:
            return _orjson.dumps(value).decode("utf-8")
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def set_langsmith_metadata_attribute(span: Span, key: str, value: Any) -> None:
    """Set a LangSmith metadata span attribute if the value is OTel-safe."""
    safe_value = otel_safe_attribute_value(value)
    if safe_value is not None:
        span.set_attribute(f"{LANGSMITH_METADATA_PREFIX}.{key}", safe_value)
