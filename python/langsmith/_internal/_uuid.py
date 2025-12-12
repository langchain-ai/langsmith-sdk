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
    """Generate a UUID from a Unix timestamp in nanoseconds and random bits.

    UUIDv7 objects feature monotonicity within a millisecond.

    Args:
        nanoseconds: Optional ns timestamp. If not provided, uses current time.
    """
    # --- 48 ---   -- 4 --   --- 12 ---   -- 2 --   --- 30 ---   - 32 -
    # unix_ts_ms | version | counter_hi | variant | counter_lo | random
    #
    # 'counter = counter_hi | counter_lo' is a 42-bit counter constructed
    # with Method 1 of RFC 9562, §6.2, and its MSB is set to 0.
    #
    # 'random' is a 32-bit random value regenerated for every new UUID.
    #
    # If multiple UUIDs are generated within the same millisecond, the LSB
    # of 'counter' is incremented by 1. When overflowing, the timestamp is
    # advanced and the counter is reset to a random 42-bit integer with MSB
    # set to 0.

    # For now, just delegate to the uuid_utils implementation
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
