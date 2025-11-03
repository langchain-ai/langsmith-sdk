"""UUID v7 implementation backported from Python 3.14+.

This module provides UUID v7 generation for Python versions < 3.14.
The implementation is taken directly from CPython's uuid.py:
https://github.com/python/cpython/blob/main/Lib/uuid.py
"""

from __future__ import annotations

import logging
import os
import time
import uuid
import warnings

logger = logging.getLogger(__name__)

# RFC 4122 version 7 flags: version bits (7 << 76) | variant bits (0x8000 << 48)
_RFC_4122_VERSION_7_FLAGS = (7 << 76) | (0x8000 << 48)

# Global state for monotonic counter
_last_timestamp_v7: int | None = None
_last_counter_v7: int = 0  # 42-bit counter


def _uuid7_get_counter_and_tail() -> tuple[int, int]:
    """Generate random counter and tail values for UUID v7."""
    rand = int.from_bytes(os.urandom(10), byteorder="big")
    # 42-bit counter with MSB set to 0
    counter = (rand >> 32) & 0x1FF_FFFF_FFFF
    # 32-bit random data
    tail = rand & 0xFFFF_FFFF
    return counter, tail


def uuid7() -> uuid.UUID:
    """Generate a UUID from a Unix timestamp in milliseconds and random bits.

    UUIDv7 objects feature monotonicity within a millisecond.

    This implementation is taken from CPython 3.14+ and provides:
    - Time-ordered UUIDs based on Unix millisecond timestamps
    - Monotonic ordering within the same millisecond via a 42-bit counter
    - Compatibility with RFC 9562 (formerly draft-ietf-uuidrev-rfc4122bis)

    Returns:
        A UUID v7 instance with time-ordered properties.
    """
    global _last_timestamp_v7
    global _last_counter_v7

    nanoseconds = time.time_ns()
    timestamp_ms = nanoseconds // 1_000_000

    if _last_timestamp_v7 is None or timestamp_ms > _last_timestamp_v7:
        counter, tail = _uuid7_get_counter_and_tail()
    else:
        if timestamp_ms < _last_timestamp_v7:
            timestamp_ms = _last_timestamp_v7 + 1
        # advance the 42-bit counter
        counter = _last_counter_v7 + 1
        if counter > 0x3FF_FFFF_FFFF:
            # advance the 48-bit timestamp
            timestamp_ms += 1
            counter, tail = _uuid7_get_counter_and_tail()
        else:
            # 32-bit random data
            tail = int.from_bytes(os.urandom(4), byteorder="big")

    unix_ts_ms = timestamp_ms & 0xFFFF_FFFF_FFFF
    counter_msbs = counter >> 30
    # keep 12 counter's MSBs and clear variant bits
    counter_hi = counter_msbs & 0x0FFF
    # keep 30 counter's LSBs and clear version bits
    counter_lo = counter & 0x3FFF_FFFF
    # ensure that the tail is always a 32-bit integer
    tail &= 0xFFFF_FFFF

    int_uuid_7 = unix_ts_ms << 80
    int_uuid_7 |= counter_hi << 64
    int_uuid_7 |= counter_lo << 32
    int_uuid_7 |= tail
    # by construction, the variant and version bits are already cleared
    int_uuid_7 |= _RFC_4122_VERSION_7_FLAGS

    # Use the public UUID constructor with int parameter
    res = uuid.UUID(int=int_uuid_7)

    # defer global update until all computations are done
    _last_timestamp_v7 = timestamp_ms
    _last_counter_v7 = counter
    return res


def is_uuid_v7(uuid_obj: uuid.UUID) -> bool:
    """Check if a UUID is version 7.

    Args:
        uuid_obj: The UUID to check.

    Returns:
        True if the UUID is version 7, False otherwise.
    """
    return uuid_obj.version == 7


def warn_if_not_uuid_v7(uuid_obj: uuid.UUID, id_type: str) -> None:
    """Warn if a UUID is not version 7.

    Args:
        uuid_obj: The UUID to check.
        id_type: The type of ID (e.g., "run_id", "trace_id") for the warning message.
    """
    if not is_uuid_v7(uuid_obj):
        warnings.warn(
            f"LangSmith now uses UUID v7 for {id_type}. The provided {id_type} "
            f"'{uuid_obj}' is UUID v{uuid_obj.version}. "
            f"Please migrate to using UUID v7. "
            f"Future versions will require UUID v7.",
            UserWarning,
            stacklevel=3,
        )
