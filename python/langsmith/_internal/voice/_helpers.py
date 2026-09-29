"""Integration-agnostic helpers shared by the voice span processors."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Optional


def build_user_message(content: str) -> dict[str, Any]:
    """Build a ``user`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "user", "content": content}


def build_assistant_message(content: str) -> dict[str, Any]:
    """Build an ``assistant`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "assistant", "content": content}


def build_tool_message(
    content: str,
    *,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
) -> dict[str, object]:
    """Build a ``tool`` result message, with its call id / name when present."""
    message: dict[str, object] = {"role": "tool", "content": content}
    if tool_call_id:
        message["tool_call_id"] = str(tool_call_id)
    if name:
        message["name"] = str(name)
    return message


def build_tool_call(call_id: str, name: str, arguments: str) -> dict[str, object]:
    """Build one OpenAI-shaped function tool call."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def build_assistant_tool_call_message(
    call_id: str, name: str, arguments: str
) -> dict[str, object]:
    """Build an assistant message containing one tool call."""
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [build_tool_call(call_id, name, arguments)],
    }


def _try_parse_json_list(value: object) -> Optional[list[object]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
    return value if isinstance(value, list) else None


def _json_text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _message_from_gen_ai_parts(
    role: str, parts: list[object]
) -> list[dict[str, object]]:
    """Convert an OTel GenAI part array into LangSmith chat messages."""
    content: list[dict[str, object]] = []
    text_parts: list[str] = []
    tool_calls: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    for raw_part in parts:
        if not isinstance(raw_part, Mapping):
            continue
        part: Mapping[object, object] = raw_part
        kind = part.get("type")
        part_content = part.get("content")
        transcript = part.get("transcript")
        uri = part.get("uri")
        call_id = part.get("id")
        tool_name = part.get("name")
        if kind == "text" and isinstance(part_content, str):
            content.append({"type": "text", "text": part_content})
            text_parts.append(part_content)
        elif (
            kind == "blob"
            and part.get("modality") == "audio"
            and isinstance(transcript, str)
        ):
            content.append({"type": "text", "text": transcript})
            text_parts.append(transcript)
        elif (
            kind == "uri"
            and part.get("modality") == "image"
            and isinstance(uri, str)
            and uri
        ):
            content.append({"type": "image_url", "image_url": {"url": uri}})
        elif (
            kind == "tool_call"
            and role == "assistant"
            and isinstance(call_id, str)
            and isinstance(tool_name, str)
        ):
            tool_calls.append(
                build_tool_call(
                    call_id,
                    tool_name,
                    _json_text(part.get("arguments", {})),
                )
            )
        elif (
            kind == "tool_call_response"
            and role == "tool"
            and isinstance(call_id, str)
            and "response" in part
        ):
            tool_results.append(
                build_tool_message(_json_text(part["response"]), tool_call_id=call_id)
            )
    messages: list[dict[str, object]] = []
    if content or tool_calls:
        message: dict[str, object] = {"role": role}
        message["content"] = (
            "\n".join(text_parts) if len(text_parts) == len(content) else content
        )
        if tool_calls:
            message["tool_calls"] = tool_calls
        messages.append(message)
    return messages + tool_results


def build_messages_from_gen_ai(
    value: object,
) -> Optional[list[dict[str, object]]]:
    """Convert OTel GenAI message envelopes into LangSmith chat messages.

    ``None`` means missing or malformed input, allowing a caller to use an older
    telemetry source as a fallback. A present empty list remains authoritative.
    """
    items = _try_parse_json_list(value)
    if items is None:
        return None
    messages: list[dict[str, object]] = []
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            continue
        item: Mapping[object, object] = raw_item
        role = item.get("role")
        parts = item.get("parts")
        if not isinstance(role, str) or role not in (
            "system",
            "developer",
            "user",
            "assistant",
            "tool",
        ):
            continue
        if isinstance(parts, list):
            messages.extend(_message_from_gen_ai_parts(role, parts))
    return messages


def build_system_messages_from_gen_ai(
    value: object,
) -> Optional[list[dict[str, object]]]:
    """Convert an OTel ``gen_ai.system_instructions`` part array to messages."""
    parts = _try_parse_json_list(value)
    if parts is None:
        return None
    return _message_from_gen_ai_parts("system", parts)


def try_parse_json_object(value: Any) -> Optional[dict]:
    """Return ``value`` parsed as a dict if it's a JSON-object string, else None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None
