"""Shared helpers: extract_run, calc_duration, format_duration, etc."""

from __future__ import annotations

import uuid
from decimal import Decimal


def calc_duration(run) -> int | None:
    """Calculate duration in milliseconds from run start/end times."""
    if run.start_time and run.end_time:
        return int((run.end_time - run.start_time).total_seconds() * 1000)
    return None


def format_duration(ms: int | None) -> str:
    """Format milliseconds as human-readable duration."""
    if ms is None:
        return "N/A"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.2f}s"


def get_trace_id(run) -> str:
    """Extract trace_id from a run object."""
    if hasattr(run, "trace_id") and run.trace_id:
        return str(run.trace_id)
    return str(run.id)


def _serialize(val):
    """Recursively make a value JSON-serializable."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return {k: _serialize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_serialize(v) for v in val]
    return val


def resolve_dataset(client, name_or_id):
    """Resolve a dataset by name or ID."""
    try:
        uid = uuid.UUID(name_or_id)
        return client.read_dataset(dataset_id=uid)
    except (ValueError, TypeError):
        return client.read_dataset(dataset_name=name_or_id)


def extract_run(run, include_metadata: bool = False, include_io: bool = False) -> dict:
    """Normalize a LangSmith Run object to a flat dict.

    Base fields are always included. Additional fields controlled by flags.
    """
    result = {
        "run_id": str(run.id),
        "trace_id": get_trace_id(run),
        "name": run.name,
        "run_type": run.run_type,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
    }

    if include_metadata:
        duration_ms = calc_duration(run)
        custom_metadata = {}
        if hasattr(run, "extra") and run.extra and isinstance(run.extra, dict):
            custom_metadata = run.extra.get("metadata", {})

        token_usage = {}
        if hasattr(run, "prompt_tokens") and run.prompt_tokens is not None:
            token_usage["prompt_tokens"] = run.prompt_tokens
        if hasattr(run, "completion_tokens") and run.completion_tokens is not None:
            token_usage["completion_tokens"] = run.completion_tokens
        if hasattr(run, "total_tokens") and run.total_tokens is not None:
            token_usage["total_tokens"] = run.total_tokens

        costs = {}
        if hasattr(run, "prompt_cost") and run.prompt_cost is not None:
            costs["prompt_cost"] = float(run.prompt_cost)
        if hasattr(run, "completion_cost") and run.completion_cost is not None:
            costs["completion_cost"] = float(run.completion_cost)
        if hasattr(run, "total_cost") and run.total_cost is not None:
            costs["total_cost"] = float(run.total_cost)

        result.update({
            "status": getattr(run, "status", None),
            "duration_ms": duration_ms,
            "custom_metadata": _serialize(custom_metadata),
            "token_usage": token_usage if token_usage else None,
            "costs": costs if costs else None,
            "tags": list(run.tags) if hasattr(run, "tags") and run.tags else None,
        })

    if include_io:
        result.update({
            "inputs": _serialize(run.inputs) if run.inputs else None,
            "outputs": _serialize(run.outputs) if run.outputs else None,
            "error": run.error if hasattr(run, "error") else None,
        })

    return result
