"""Deterministic trace sampling, kept consistent across LangSmith SDKs."""

from __future__ import annotations

from typing import Any, Optional

import xxhash

_SAMPLING_HASH_MODULUS = 1_000_000


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
    # XXH3-128 over the UTF-8 bytes, matching the JS SDK's vendored xxh3-ts.
    # The identifier is sampled in when its fraction of the modulus falls below
    # the rate, which is also expressed in [0, 1).
    digest = xxhash.xxh3_128(str(identifier).lower().encode("utf-8")).intdigest()
    bucket = digest % _SAMPLING_HASH_MODULUS
    return bucket / _SAMPLING_HASH_MODULUS < sampling_rate
