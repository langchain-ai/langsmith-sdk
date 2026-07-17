"""Public UUID v7 helpers.

These helpers expose utilities for generating UUID v7 identifiers in user code.
"""

from __future__ import annotations

import datetime as _dt
import uuid as _uuid

from ._internal._uuid import uuid7 as _uuid7
from ._internal._uuid import uuid7_deterministic as _uuid7_deterministic


def uuid7() -> _uuid.UUID:
    """Generate a random UUID v7.

    Returns:
        uuid.UUID: A random, RFC 9562-compliant UUID v7.
    """
    return _uuid7()


def uuid7_from_datetime(dt: _dt.datetime) -> _uuid.UUID:
    """Generate a UUID v7 from a datetime.

    Args:
        dt: A timezone-aware datetime. If naive, it is treated as UTC.

    Returns:
        uuid.UUID: A UUID v7 whose timestamp corresponds to the provided time.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    nanoseconds = int(dt.timestamp() * 1_000_000_000)
    return _uuid7(nanoseconds)


def compute_run_id_for_replica(
    run_id: _uuid.UUID | str, project_name: str
) -> _uuid.UUID:
    """Generate the run ID used for a tracing replica.

    Use this ID when creating feedback for a run in a replica project. The
    result matches the deterministic ID remapping performed when LangSmith
    sends a UUID v7 run to a replica whose project differs from the run's
    original project.

    Args:
        run_id: The original run ID.
        project_name: The destination replica project name.

    Returns:
        uuid.UUID: The run ID used in the replica project.
    """
    return _uuid7_deterministic(_uuid.UUID(str(run_id)), project_name)


__all__ = ["compute_run_id_for_replica", "uuid7", "uuid7_from_datetime"]
