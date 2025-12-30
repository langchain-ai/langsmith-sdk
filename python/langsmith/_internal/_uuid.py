"""UUID helpers backed by uuid-utils."""

from __future__ import annotations

import hashlib
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


def uuid7_deterministic(original_id: uuid.UUID, key: str) -> uuid.UUID:
    """Generate a deterministic UUID7 derived from an original UUID and a key.

    This function creates a new UUID that:
    - Preserves the timestamp from the original UUID if it's UUID v7
    - Uses current time if the original is not UUID v7
    - Uses deterministic "random" bits derived from hashing the original + key
    - Is valid UUID v7 format

    This is used for creating replica IDs that maintain time-ordering properties
    while being deterministic across distributed systems.

    Args:
        original_id: The source UUID (ideally UUID v7 to preserve timestamp).
        key: A string key used for deterministic derivation (e.g., project name).

    Returns:
        A new UUID v7 with preserved timestamp (if original is v7) and
        deterministic random bits.

    Example:
        >>> original = uuid7()
        >>> replica_id = uuid7_deterministic(original, "replica-project")
        >>> # Same inputs always produce same output
        >>> assert uuid7_deterministic(original, "replica-project") == replica_id
    """
    import time

    # Generate deterministic bytes from hash of original + key
    hash_input = f"{original_id}:{key}".encode()
    h = hashlib.sha256(hash_input).digest()

    # Build new UUID7:
    # UUID7 structure (RFC 9562):
    # [0-5]  48 bits: unix_ts_ms (timestamp in milliseconds)
    # [6]    4 bits: version (0111 = 7) + 4 bits rand_a
    # [7]    8 bits: rand_a (continued)
    # [8]    2 bits: variant (10) + 6 bits rand_b
    # [9-15] 56 bits: rand_b (continued)

    b = bytearray(16)

    # Check if original is UUID v7 - if so, preserve its timestamp
    # If not, use current time to ensure the derived UUID has a valid timestamp
    if is_uuid_v7(original_id):
        # Preserve timestamp from original UUID7 (bytes 0-5)
        b[0:6] = original_id.bytes[0:6]
    else:
        # Generate fresh timestamp for non-UUID7 inputs
        # This matches CPython 3.14's uuid7() implementation:
        # timestamp_ms = time.time_ns() // 1_000_000
        # Then convert to big-endian bytes
        timestamp_ms = time.time_ns() // 1_000_000
        # Mask to 48 bits and convert to big-endian bytes
        unix_ts_ms = timestamp_ms & 0xFFFF_FFFF_FFFF
        b[0:6] = unix_ts_ms.to_bytes(6, "big")

    # Set version 7 (0111) in high nibble + 4 bits from hash
    b[6] = 0x70 | (h[0] & 0x0F)

    # rand_a continued (8 bits from hash)
    b[7] = h[1]

    # Set variant (10) in high 2 bits + 6 bits from hash
    b[8] = 0x80 | (h[2] & 0x3F)

    # rand_b (56 bits = 7 bytes from hash)
    b[9:16] = h[3:10]

    return uuid.UUID(bytes=bytes(b))
