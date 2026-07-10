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
