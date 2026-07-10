"""Small pure helpers for the Pipecat → LangSmith span processor."""

from __future__ import annotations

import json
from typing import Any

from langsmith._internal.voice._helpers import (
    build_assistant_message,
    try_parse_json_object,
)


def parse_llm_messages(input_data: Any) -> list[dict[str, Any]]:
    """Parse a Pipecat ``llm`` span's ``input`` (a JSON message list) to dicts."""
    try:
        raw = json.loads(input_data)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    return [m for m in raw if isinstance(m, dict)]


def _as_int(value: Any) -> Any:
    """Coerce a numeric span-attribute value to ``int``, or ``None`` otherwise."""
    return int(value) if isinstance(value, (int, float)) else None


def extract_tts_characters(attributes: dict[str, Any]) -> Any:
    """Read ``metrics.character_count`` from a Pipecat ``tts`` span.

    That count is the billable TTS unit (synthesis is priced per character), so
    it is lifted onto the span as the token count a per-character price entry
    multiplies. ``None`` when the attribute is absent or non-numeric.
    """
    return _as_int(attributes.get("metrics.character_count"))


def extract_llm_token_details(
    attributes: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    """Split Pipecat's non-standard LLM cache/reasoning keys into token detail.

    Pipecat writes plain ``gen_ai.usage.input_tokens`` / ``output_tokens`` (which
    the ingester reads as-is) but reports cache and reasoning tokens under
    vendor-specific keys the ingester ignores. This recovers them into the
    canonical ``(input_detail, output_detail)`` breakdown so cached input and
    reasoning output are priced at their own rates. Empty dicts when none apply.
    """
    input_detail: dict[str, int] = {}
    if (
        v := _as_int(attributes.get("gen_ai.usage.cache_read.input_tokens"))
    ) is not None:
        input_detail["cache_read"] = v
    if (
        v := _as_int(attributes.get("gen_ai.usage.cache_creation.input_tokens"))
    ) is not None:
        input_detail["cache_creation"] = v
    output_detail: dict[str, int] = {}
    if (v := _as_int(attributes.get("gen_ai.usage.reasoning_tokens"))) is not None:
        output_detail["reasoning"] = v
    return input_detail, output_detail


def build_completion_message(output_data: Any) -> dict[str, Any]:
    """Build the assistant completion for a Pipecat ``llm`` span.

    A structured response carrying ``tool_calls`` is forwarded in its OpenAI
    shape; anything else becomes plain assistant text.
    """
    parsed = try_parse_json_object(output_data)
    if isinstance(parsed, dict) and parsed.get("tool_calls"):
        return {"role": "assistant", **parsed}
    content = output_data if isinstance(output_data, str) else str(output_data)
    return build_assistant_message(content)
