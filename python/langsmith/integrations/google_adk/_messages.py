"""Message serialization for Google ADK."""

from __future__ import annotations

import base64
import json
from typing import Any


def convert_adk_content_to_langsmith(content: Any) -> list[dict[str, Any]]:
    """Convert ADK Content/Part objects to serializable format."""
    if content is None:
        return []
    if hasattr(content, "parts"):
        parts = content.parts
    elif isinstance(content, list):
        parts = content
    else:
        return [_serialize_part(content)]
    return [_serialize_part(part) for part in parts if part is not None]


def _serialize_part(part: Any) -> dict[str, Any]:
    """Serialize a single Part."""
    if isinstance(part, dict):
        return part

    if hasattr(part, "inline_data") and part.inline_data:
        data = getattr(part.inline_data, "data", None)
        mime_type = getattr(part.inline_data, "mime_type", "application/octet-stream")
        if data is not None:
            encoded = (
                base64.b64encode(data).decode("utf-8")
                if isinstance(data, bytes)
                else str(data)
            )
            return {"type": "image", "data": encoded, "mime_type": mime_type}

    if hasattr(part, "file_data") and part.file_data:
        return {
            "type": "file",
            "file_uri": getattr(part.file_data, "file_uri", None),
            "mime_type": getattr(part.file_data, "mime_type", None),
        }

    if hasattr(part, "function_call") and part.function_call:
        fc = part.function_call
        return {
            "type": "tool_use",
            "name": getattr(fc, "name", "unknown"),
            "input": dict(getattr(fc, "args", None) or {}),
        }

    if hasattr(part, "function_response") and part.function_response:
        fr = part.function_response
        return {
            "type": "tool_result",
            "name": getattr(fr, "name", "unknown"),
            "content": _safe_serialize(getattr(fr, "response", None)),
        }

    if hasattr(part, "text") and part.text is not None:
        return {"type": "text", "text": str(part.text)}

    if hasattr(part, "executable_code") and part.executable_code:
        code = part.executable_code
        return {
            "type": "executable_code",
            "language": getattr(code, "language", "python"),
            "code": getattr(code, "code", ""),
        }

    if hasattr(part, "code_execution_result") and part.code_execution_result:
        result = part.code_execution_result
        return {
            "type": "code_execution_result",
            "outcome": getattr(result, "outcome", "unknown"),
            "output": getattr(result, "output", ""),
        }

    if hasattr(part, "thought") and part.thought is not None:
        return {"type": "thinking", "thinking": str(part.thought)}

    return _safe_serialize(part)


def _safe_serialize(obj: Any) -> Any:
    """Safely serialize an object to JSON-compatible format."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj]
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {k: _safe_serialize(v) for k, v in obj.__dict__.items()}
        except Exception:
            pass
    return str(obj)


def convert_llm_request_to_messages(llm_request: Any) -> list[dict[str, Any]]:
    """Convert LlmRequest to OpenAI-compatible message format."""
    messages: list[dict[str, Any]] = []

    # Extract system instruction from config
    config = getattr(llm_request, "config", None)
    if config:
        sys_inst = getattr(config, "system_instruction", None)
        if sys_inst:
            messages.append({"role": "system", "content": str(sys_inst)})

    contents = getattr(llm_request, "contents", None)
    if not contents:
        return messages

    for content in contents:
        role = getattr(content, "role", "user")
        if role == "model":
            role = "assistant"

        parts = convert_adk_content_to_langsmith(content)
        text_parts, tool_calls, tool_results = [], [], []

        for part in parts:
            t = part.get("type")
            if t == "text":
                text_parts.append(part.get("text", ""))
            elif t == "tool_use":
                tool_calls.append(part)
            elif t == "tool_result":
                tool_results.append(part)
            else:
                text_parts.append(str(part))

        if tool_calls and role == "assistant":
            messages.append(
                {
                    "role": "assistant",
                    "content": " ".join(text_parts) if text_parts else None,
                    "tool_calls": [
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("input", {})),
                            },
                        }
                        for i, tc in enumerate(tool_calls)
                    ],
                }
            )
        elif tool_results:
            for tr in tool_results:
                c = tr.get("content")
                messages.append(
                    {
                        "role": "tool",
                        "name": tr.get("name", ""),
                        "content": (
                            json.dumps(c) if isinstance(c, dict) else str(c or "")
                        ),
                    }
                )
        else:
            messages.append(
                {
                    "role": role,
                    "content": " ".join(text_parts) if text_parts else "",
                }
            )

    return messages


def has_function_calls(llm_response: Any) -> bool:
    """Check if LlmResponse contains function calls."""
    content = getattr(llm_response, "content", None)
    if not content:
        return False
    parts = convert_adk_content_to_langsmith(content)
    return any(p.get("type") == "tool_use" for p in parts)


def has_function_response_in_request(llm_request: Any) -> bool:
    """Check if LlmRequest contains function responses (tool results)."""
    for content in getattr(llm_request, "contents", None) or []:
        parts = convert_adk_content_to_langsmith(content)
        if any(p.get("type") == "tool_result" for p in parts):
            return True
    return False
