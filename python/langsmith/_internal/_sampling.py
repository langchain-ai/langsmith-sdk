"""Deterministic trace sampling, kept consistent across LangSmith SDKs."""

from __future__ import annotations

from typing import Any, Optional

_SAMPLING_HASH_MODULUS = 1_000_000
_FNV_64_OFFSET_BASIS = 14_695_981_039_346_656_037
_FNV_64_PRIME = 1_099_511_628_211
_FNV_64_MASK = (1 << 64) - 1


def _fnv_1a_64(value: str) -> int:
    """Compute the 64-bit FNV-1a hash of a string.

    Implemented explicitly so the result matches other SDKs byte-for-byte,
    keeping sampling decisions consistent across SDKs.
    """
    hash_value = _FNV_64_OFFSET_BASIS
    for byte in value.encode("utf-8"):
        hash_value ^= byte
        hash_value = (hash_value * _FNV_64_PRIME) & _FNV_64_MASK
    return hash_value


def is_sampled_by_id(identifier: Any, sampling_rate: Optional[float]) -> bool:
    """Decide whether `identifier` is sampled in at `sampling_rate`.

    The decision is a pure function of the identifier, so every process and
    every SDK agrees on it, and a run's create and patch never disagree.
    """
    if sampling_rate is None or sampling_rate >= 1:
        return True
    if sampling_rate <= 0:
        return False
    if identifier is None:
        return True
    # The identifier is sampled in when its fraction of the modulus falls below
    # the rate, which is also expressed in [0, 1).
    bucket = _fnv_1a_64(str(identifier).lower()) % _SAMPLING_HASH_MODULUS
    return bucket / _SAMPLING_HASH_MODULUS < sampling_rate
