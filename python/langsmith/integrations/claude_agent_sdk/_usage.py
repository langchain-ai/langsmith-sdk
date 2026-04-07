"""Token usage utilities for Claude Agent SDK.

Normalizes raw Anthropic usage dicts into the canonical ``usage_metadata``
format expected by LangSmith.  The key Anthropic-specific behavior is that
cache tokens (``cache_read_input_tokens`` and ``cache_creation_input_tokens``)
are **additive** — they are *not* included in the raw ``input_tokens`` value,
so they must be summed in.

The canonical shape matches the JS LangSmith SDK's ``createUsageMetadata``:

.. code-block:: json

   {
     "input_tokens": 21400,
     "output_tokens": 7,
     "total_tokens": 21407,
     "input_token_details": {
       "cache_read": 21375,
       "ephemeral_5m_input_tokens": 0,
       "ephemeral_1hr_input_tokens": 0
     }
   }
"""

from typing import Any


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def extract_usage_metadata(usage: Any) -> dict[str, Any]:
    """Normalize a raw Anthropic usage dict into canonical ``usage_metadata``.

    Anthropic cache tokens are **additive**: ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` are not included in the raw
    ``input_tokens``, so we sum them in to get the true input total.
    """
    if not usage:
        return {}

    get = (
        usage.get if isinstance(usage, dict) else lambda k, d=None: getattr(usage, k, d)
    )

    raw_input = _to_int(get("input_tokens"))
    output_tokens = _to_int(get("output_tokens"))

    # Build input_token_details from cache fields
    input_token_details: dict[str, int] = {}

    cache_read = _to_int(get("cache_read_input_tokens"))
    if cache_read:
        input_token_details["cache_read"] = cache_read

    # Structured cache_creation (with ephemeral breakdown) takes precedence
    # over the flat cache_creation_input_tokens field.
    cache_creation = get("cache_creation")
    if isinstance(cache_creation, dict):
        eph_5m = _to_int(cache_creation.get("ephemeral_5m_input_tokens"))
        eph_1h = _to_int(cache_creation.get("ephemeral_1h_input_tokens"))
        if eph_5m:
            input_token_details["ephemeral_5m_input_tokens"] = eph_5m
        if eph_1h:
            input_token_details["ephemeral_1hr_input_tokens"] = eph_1h
    else:
        # Flat/legacy field — assume 5-minute cache
        flat_cache_create = _to_int(get("cache_creation_input_tokens"))
        if flat_cache_create:
            input_token_details["ephemeral_5m_input_tokens"] = flat_cache_create

    # Sum cache tokens into input_tokens (Anthropic cache tokens are additive)
    cache_token_sum = sum(input_token_details.values())
    adjusted_input = raw_input + cache_token_sum
    total_tokens = adjusted_input + output_tokens

    meta: dict[str, Any] = {
        "input_tokens": adjusted_input,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }
    if input_token_details:
        meta["input_token_details"] = input_token_details

    return meta
