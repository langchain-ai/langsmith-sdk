"""UUID helpers backed by uuid-utils."""

from __future__ import annotations

import uuid
import warnings
from typing import Final

from uuid_utils.compat import uuid7 as _uuid_utils_uuid7

_NANOS_PER_SECOND: Final = 1_000_000_000


def _to_timestamp_and_nanos(nanoseconds: int) -> tuple[int, int]:
    """Split a nanosecond timestamp into seconds and remaining nanoseconds."""
    seconds, nanos = divmod(nanoseconds, _NANOS_PER_SECOND)
    return seconds, nanos


def uuid7(nanoseconds: int | None = None) -> uuid.UUID:
    """Generate a UUIDv7 using uuid-utils, optionally at a given timestamp."""
    if nanoseconds is None:
        return _uuid_utils_uuid7()
    seconds, nanos = _to_timestamp_and_nanos(nanoseconds)
    return _uuid_utils_uuid7(timestamp=seconds, nanos=nanos)


def is_uuid_v7(uuid_obj: uuid.UUID) -> bool:
    """Check if a UUID is version 7.

    Args:
        uuid_obj: The UUID to check.

    Returns:
        True if the UUID is version 7, False otherwise.
    """
    return uuid_obj.version == 7


_UUID_V7_WARNING_EMITTED = False


def warn_if_not_uuid_v7(uuid_obj: uuid.UUID, id_type: str) -> None:
    """Warn if a UUID is not version 7.

    Args:
        uuid_obj: The UUID to check.
        id_type: The type of ID (e.g., "run_id", "trace_id") for the warning message.
    """
    global _UUID_V7_WARNING_EMITTED
    if not is_uuid_v7(uuid_obj) and not _UUID_V7_WARNING_EMITTED:
        _UUID_V7_WARNING_EMITTED = True
        warnings.warn(
            (
                "LangSmith now uses UUID v7 for run and trace identifiers. "
                "This warning appears when passing custom IDs. "
                "Please use: from langsmith import uuid7\n"
                "            id = uuid7()\n"
                "Future versions will require UUID v7."
            ),
            UserWarning,
            stacklevel=3,
        )
