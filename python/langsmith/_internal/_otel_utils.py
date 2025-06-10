"""Utilities for OpenTelemetry integration with LangSmith."""

from __future__ import annotations

from typing import Optional
from uuid import UUID


def uuid_to_otel_trace_id(uuid_val: UUID) -> str:
    """Convert a UUID to an OpenTelemetry trace ID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        A 32-character lowercase hex string representing the trace ID.
    """
    # UUIDs are already 128 bits, which is what OTel trace IDs need
    # Convert to 32-character lowercase hex string
    return uuid_val.hex


def uuid_to_otel_span_id(uuid_val: UUID) -> str:
    """Convert a UUID to an OpenTelemetry span ID.

    Since span IDs are 64 bits (8 bytes) and UUIDs are 128 bits (16 bytes),
    we need to derive a 64-bit value deterministically from the UUID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        A 16-character lowercase hex string representing the span ID.
    """
    # Use the first 8 bytes of the UUID for deterministic span ID
    uuid_bytes = uuid_val.bytes
    span_id_bytes = uuid_bytes[:8]
    # Convert to 16-character lowercase hex string
    return span_id_bytes.hex()


def otel_trace_id_to_int(trace_id: str) -> int:
    """Convert an OpenTelemetry trace ID string to an integer.

    Args:
        trace_id: 32-character hex string representing the trace ID.

    Returns:
        Integer representation of the trace ID.
    """
    return int(trace_id, 16)


def otel_span_id_to_int(span_id: str) -> int:
    """Convert an OpenTelemetry span ID string to an integer.

    Args:
        span_id: 16-character hex string representing the span ID.

    Returns:
        Integer representation of the span ID.
    """
    return int(span_id, 16)


def get_otel_trace_id_from_uuid(uuid_val: UUID) -> int:
    """Get OpenTelemetry trace ID as integer from UUID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        Integer representation of the trace ID.
    """
    trace_id_hex = uuid_to_otel_trace_id(uuid_val)
    return otel_trace_id_to_int(trace_id_hex)


def get_otel_span_id_from_uuid(uuid_val: UUID) -> int:
    """Get OpenTelemetry span ID as integer from UUID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        Integer representation of the span ID.
    """
    span_id_hex = uuid_to_otel_span_id(uuid_val)
    return otel_span_id_to_int(span_id_hex)


def get_otel_trace_id_from_run_tree() -> Optional[int]:
    """Get OpenTelemetry trace ID from current LangSmith run tree.

    Returns:
        Integer representation of the trace ID, or None if no current run tree.
    """
    from langsmith.run_helpers import get_current_run_tree

    current_run = get_current_run_tree()
    if current_run is None:
        return None

    return get_otel_trace_id_from_uuid(current_run.trace_id)


def get_otel_span_id_from_run_tree() -> Optional[int]:
    """Get OpenTelemetry span ID from current LangSmith run tree.

    Returns:
        Integer representation of the span ID, or None if no current run tree.
    """
    from langsmith.run_helpers import get_current_run_tree

    current_run = get_current_run_tree()
    if current_run is None:
        return None

    return get_otel_span_id_from_uuid(current_run.id)


def get_otel_parent_span_id_from_run_tree() -> Optional[int]:
    """Get OpenTelemetry parent span ID from current LangSmith run tree.

    Returns:
        Integer representation of the parent span ID, or None if no parent.
    """
    from langsmith.run_helpers import get_current_run_tree

    current_run = get_current_run_tree()
    if current_run is None or current_run.parent_run_id is None:
        return None

    return get_otel_span_id_from_uuid(current_run.parent_run_id)
