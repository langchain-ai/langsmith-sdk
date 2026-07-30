"""Shared token-usage normalization for Gemini integrations."""

from __future__ import annotations

from typing import Any


def _audio_tokens(details: Any) -> int | None:
    """Sum the audio token count from a Gemini modality-details sequence."""
    if not isinstance(details, (list, tuple)):
        return None
    total = 0
    found = False
    for entry in details:
        modality = getattr(entry, "modality", None)
        modality = getattr(modality, "value", modality)
        count = getattr(entry, "token_count", None)
        if str(modality).upper() == "AUDIO" and isinstance(count, int):
            total += count
            found = True
    return total if found else None


def normalize_gemini_usage_metadata(usage: Any) -> dict[str, Any] | None:
    """Map a Gemini usage object onto LangSmith's canonical token metadata.

    Gemini's direct Live API uses ``response_*`` output fields, while ADK and
    older generated response types use ``candidates_*``. Only the known token
    fields below are read so provider objects cannot add arbitrary metadata.
    """
    if usage is None:
        return None

    result: dict[str, Any] = {}
    for key, attrs in (
        ("input_tokens", ("prompt_token_count",)),
        ("output_tokens", ("response_token_count", "candidates_token_count")),
        ("total_tokens", ("total_token_count",)),
    ):
        for attr in attrs:
            value = getattr(usage, attr, None)
            if isinstance(value, int):
                result[key] = value
                break

    input_details: dict[str, int] = {}
    if (
        audio := _audio_tokens(getattr(usage, "prompt_tokens_details", None))
    ) is not None:
        input_details["audio"] = audio
    if isinstance(cached := getattr(usage, "cached_content_token_count", None), int):
        input_details["cache_read"] = cached
    if input_details:
        result["input_token_details"] = input_details

    output_details: dict[str, int] = {}
    response_details = getattr(usage, "response_tokens_details", None)
    if response_details is None:
        response_details = getattr(usage, "candidates_tokens_details", None)
    if (audio := _audio_tokens(response_details)) is not None:
        output_details["audio"] = audio
    if isinstance(reasoning := getattr(usage, "thoughts_token_count", None), int):
        output_details["reasoning"] = reasoning
    if output_details:
        result["output_token_details"] = output_details

    return result or None
