"""Shared token-usage mapping.

``_create_usage_metadata`` normalizes an OpenAI-shaped token ``usage`` dict into
LangSmith's canonical :class:`~langsmith.schemas.UsageMetadata`. It lives here —
not in ``langsmith.wrappers._openai`` — so integrations can reuse it without
importing the ``wrappers`` package (whose ``__init__`` eagerly imports a
deprecated tombstone that warns at import time). ``wrappers._openai`` re-exports
it for backwards compatibility.
"""

from __future__ import annotations

from typing import Optional

from langsmith.schemas import InputTokenDetails, OutputTokenDetails, UsageMetadata


def _create_usage_metadata(
    oai_token_usage: dict, service_tier: Optional[str] = None
) -> UsageMetadata:
    recognized_service_tier = (
        service_tier if service_tier in ["priority", "flex"] else None
    )
    service_tier_prefix = (
        f"{recognized_service_tier}_" if recognized_service_tier else ""
    )

    input_tokens = (
        oai_token_usage.get("prompt_tokens") or oai_token_usage.get("input_tokens") or 0
    )
    output_tokens = (
        oai_token_usage.get("completion_tokens")
        or oai_token_usage.get("output_tokens")
        or 0
    )
    total_tokens = oai_token_usage.get("total_tokens") or input_tokens + output_tokens
    input_token_details: dict = {
        "audio": (
            oai_token_usage.get("prompt_tokens_details")
            or oai_token_usage.get("input_tokens_details")
            or {}
        ).get("audio_tokens"),
        f"{service_tier_prefix}cache_read": (
            oai_token_usage.get("prompt_tokens_details")
            or oai_token_usage.get("input_tokens_details")
            or {}
        ).get("cached_tokens"),
    }
    output_token_details: dict = {
        "audio": (
            oai_token_usage.get("completion_tokens_details")
            or oai_token_usage.get("output_tokens_details")
            or {}
        ).get("audio_tokens"),
        f"{service_tier_prefix}reasoning": (
            oai_token_usage.get("completion_tokens_details")
            or oai_token_usage.get("output_tokens_details")
            or {}
        ).get("reasoning_tokens"),
    }

    if recognized_service_tier:
        # Avoid counting cache read and reasoning tokens towards the
        # service tier token count since service tier tokens are already
        # priced differently
        input_token_details[recognized_service_tier] = input_tokens - (
            input_token_details.get(f"{service_tier_prefix}cache_read") or 0
        )
        output_token_details[recognized_service_tier] = output_tokens - (
            output_token_details.get(f"{service_tier_prefix}reasoning") or 0
        )

    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_token_details=InputTokenDetails(
            **{k: v for k, v in input_token_details.items() if v is not None}
        ),
        output_token_details=OutputTokenDetails(
            **{k: v for k, v in output_token_details.items() if v is not None}
        ),
    )
