"""Small pure helpers for the Pipecat → LangSmith span processor."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

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


def extract_llm_usage(attributes: dict[str, Any]) -> dict[str, Any]:
    """Read Pipecat's ``gen_ai.usage.*`` span keys into ``set_usage`` kwargs."""
    usage: dict[str, Any] = {}
    if (v := _as_int(attributes.get("gen_ai.usage.input_tokens"))) is not None:
        usage["input_tokens"] = v
    if (v := _as_int(attributes.get("gen_ai.usage.output_tokens"))) is not None:
        usage["output_tokens"] = v
    input_detail: dict[str, int] = {}
    if (
        v := _as_int(attributes.get("gen_ai.usage.cache_read.input_tokens"))
    ) is not None:
        input_detail["cache_read"] = v
    if (
        v := _as_int(attributes.get("gen_ai.usage.cache_creation.input_tokens"))
    ) is not None:
        input_detail["cache_creation"] = v
    if input_detail:
        usage["input_token_details"] = input_detail
    if (v := _as_int(attributes.get("gen_ai.usage.reasoning_tokens"))) is not None:
        usage["output_token_details"] = {"reasoning": v}
    return usage


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


def iso_to_ns(timestamp: str) -> int:
    """Parse an ISO 8601 timestamp to epoch nanoseconds (0 if unparseable)."""
    try:
        return int(datetime.fromisoformat(timestamp).timestamp() * 1e9)
    except (ValueError, TypeError):
        return 0


def tool_message_key(message: dict[str, Any]) -> Optional[tuple]:
    """Dedup identity for a tool-round-trip message, or ``None`` otherwise.

    Only assistant tool-call messages and tool-result messages carry one;
    user turns and plain assistant replies (owned by other sources) return
    ``None`` so they are ignored here.
    """
    tool_calls = message.get("tool_calls")
    if tool_calls:
        return ("assistant_tool_call", tuple(str(c.get("id")) for c in tool_calls))
    if message.get("role") == "tool":
        return ("tool_result", str(message.get("tool_call_id")))
    return None
