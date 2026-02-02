"""Message processing and content serialization for Google ADK."""

import base64
from typing import Any


def convert_adk_content_to_langsmith(content: Any) -> list[dict[str, Any]]:
    """Convert ADK Content/Part objects to LangSmith message format.

    Args:
        content: ADK Content object or list of Parts.

    Returns:
        A list of serializable message content blocks.
    """
    if content is None:
        return []

    # Handle Content object with parts attribute
    if hasattr(content, "parts"):
        parts = content.parts
    elif isinstance(content, list):
        parts = content
    else:
        # Single part or primitive
        return [_serialize_part(content)]

    return [_serialize_part(part) for part in parts if part is not None]


def _serialize_part(part: Any) -> dict[str, Any]:
    """Serialize a single Part, handling binary data and various types.

    Args:
        part: A Part object from Google ADK.

    Returns:
        A serializable dictionary representation.
    """
    # Already a dict - return as-is
    if isinstance(part, dict):
        return part

    # Handle inline_data (binary content like images)
    if hasattr(part, "inline_data") and part.inline_data:
        inline_data = part.inline_data
        data = getattr(inline_data, "data", None)
        mime_type = getattr(inline_data, "mime_type", "application/octet-stream")

        if data is not None:
            # Convert bytes to base64 for JSON serialization
            if isinstance(data, bytes):
                encoded_data = base64.b64encode(data).decode("utf-8")
            else:
                encoded_data = str(data)

            return {
                "type": "image",
                "data": encoded_data,
                "mime_type": mime_type,
            }

    # Handle file_data (references to files)
    if hasattr(part, "file_data") and part.file_data:
        file_data = part.file_data
        return {
            "type": "file",
            "file_uri": getattr(file_data, "file_uri", None),
            "mime_type": getattr(file_data, "mime_type", None),
        }

    # Handle function_call (tool invocations)
    if hasattr(part, "function_call") and part.function_call:
        func_call = part.function_call
        args = getattr(func_call, "args", None)
        return {
            "type": "tool_use",
            "name": getattr(func_call, "name", "unknown"),
            "input": dict(args) if args else {},
        }

    # Handle function_response (tool results)
    if hasattr(part, "function_response") and part.function_response:
        func_response = part.function_response
        response = getattr(func_response, "response", None)
        return {
            "type": "tool_result",
            "name": getattr(func_response, "name", "unknown"),
            "content": _safe_serialize(response),
        }

    # Handle text content
    if hasattr(part, "text") and part.text is not None:
        return {"type": "text", "text": str(part.text)}

    # Handle executable_code
    if hasattr(part, "executable_code") and part.executable_code:
        code = part.executable_code
        return {
            "type": "executable_code",
            "language": getattr(code, "language", "python"),
            "code": getattr(code, "code", ""),
        }

    # Handle code_execution_result
    if hasattr(part, "code_execution_result") and part.code_execution_result:
        result = part.code_execution_result
        return {
            "type": "code_execution_result",
            "outcome": getattr(result, "outcome", "unknown"),
            "output": getattr(result, "output", ""),
        }

    # Handle thought/thinking blocks
    if hasattr(part, "thought") and part.thought is not None:
        return {"type": "thinking", "thinking": str(part.thought)}

    # Fallback: try to convert to dict or string
    return _safe_serialize(part)


def _safe_serialize(obj: Any) -> Any:
    """Safely serialize an object to a JSON-compatible format.

    Args:
        obj: Any object to serialize.

    Returns:
        A JSON-serializable representation.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")

    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj]

    # Try to convert to dict if possible
    if hasattr(obj, "__dict__"):
        try:
            return {k: _safe_serialize(v) for k, v in obj.__dict__.items()}
        except Exception:
            pass

    # Try model_dump for Pydantic models
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass

    # Final fallback to string
    return str(obj)


def convert_llm_request_to_messages(llm_request: Any) -> list[dict[str, Any]]:
    """Convert LlmRequest contents to OpenAI-compatible message format.

    This formats messages in a way that LangSmith UI can render properly:
    - User messages with text content
    - Assistant messages with tool_calls array (not in content)
    - Tool messages with role="tool" for tool results

    Args:
        llm_request: The LlmRequest object from Google ADK.

    Returns:
        A list of messages in OpenAI-compatible format.
    """
    import json

    messages: list[dict[str, Any]] = []

    contents = getattr(llm_request, "contents", None)
    if not contents:
        return messages

    for content in contents:
        role = getattr(content, "role", "user")
        parts = convert_adk_content_to_langsmith(content)

        # Separate text from tool_use and tool_result
        text_parts = []
        tool_calls = []
        tool_results = []

        for part in parts:
            part_type = part.get("type")
            if part_type == "text":
                text_parts.append(part.get("text", ""))
            elif part_type == "tool_use":
                tool_calls.append(part)
            elif part_type == "tool_result":
                tool_results.append(part)
            else:
                # Other types - include as text representation
                text_parts.append(str(part))

        # Map Google roles to OpenAI standard
        if role == "model":
            role = "assistant"

        # Build message based on content
        if tool_calls and role == "assistant":
            # Assistant message with tool calls - use OpenAI format
            msg: dict[str, Any] = {
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
            messages.append(msg)
        elif tool_results:
            # Tool result messages - use role="tool"
            for tr in tool_results:
                content_val = tr.get("content")
                if isinstance(content_val, dict):
                    content_str = json.dumps(content_val)
                else:
                    content_str = str(content_val) if content_val else ""
                messages.append({
                    "role": "tool",
                    "name": tr.get("name", ""),
                    "content": content_str,
                })
        else:
            # Regular message with text content
            messages.append({
                "role": role,
                "content": " ".join(text_parts) if text_parts else "",
            })

    return messages


def extract_text_from_response(llm_response: Any) -> str | None:
    """Extract text content from an LlmResponse.

    Args:
        llm_response: The LlmResponse object from Google ADK.

    Returns:
        The concatenated text content or None if no text found.
    """
    content = getattr(llm_response, "content", None)
    if not content:
        return None

    parts = convert_adk_content_to_langsmith(content)
    text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]

    return "".join(text_parts) if text_parts else None


def has_function_calls(llm_response: Any) -> bool:
    """Check if an LlmResponse contains function calls.

    Args:
        llm_response: The LlmResponse object from Google ADK.

    Returns:
        True if the response contains function calls.
    """
    content = getattr(llm_response, "content", None)
    if not content:
        return False

    parts = convert_adk_content_to_langsmith(content)
    return any(p.get("type") == "tool_use" for p in parts)


def has_function_response_in_request(llm_request: Any) -> bool:
    """Check if an LlmRequest contains function responses.

    Args:
        llm_request: The LlmRequest object from Google ADK.

    Returns:
        True if the request contains function responses (tool results).
    """
    contents = getattr(llm_request, "contents", None)
    if not contents:
        return False

    for content in contents:
        parts = convert_adk_content_to_langsmith(content)
        if any(p.get("type") == "tool_result" for p in parts):
            return True

    return False
