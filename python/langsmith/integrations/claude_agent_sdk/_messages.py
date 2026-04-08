"""Message processing and content serialization for Claude Agent SDK."""

from typing import Any


def _extract_tool_result_text(content: Any) -> str:
    """Extract text content from tool result content blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
            elif hasattr(item, "text"):
                texts.append(getattr(item, "text", ""))
        return "\n".join(texts) if texts else str(content)
    return str(content)


def flatten_content_blocks(content: Any) -> Any:
    """Convert SDK content blocks into serializable dicts using explicit type checks."""
    if not isinstance(content, list):
        return content

    result = []
    for block in content:
        block_type = type(block).__name__

        # Handle known Claude SDK block types
        if block_type == "TextBlock":
            result.append(
                {
                    "type": "text",
                    "text": getattr(block, "text", ""),
                }
            )
        elif block_type == "ThinkingBlock":
            result.append(
                {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", ""),
                    "signature": getattr(block, "signature", ""),
                }
            )
        elif block_type == "ToolUseBlock":
            result.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", None),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                }
            )
        elif block_type == "ToolResultBlock":
            # Extract text from nested content for tool results
            tool_content = getattr(block, "content", None)
            content_text = _extract_tool_result_text(tool_content)
            result.append(
                {
                    "type": "tool_result",
                    "tool_use_id": getattr(block, "tool_use_id", None),
                    "content": content_text,
                    "is_error": getattr(block, "is_error", False),
                }
            )
        else:
            result.append(block)
    return result


def unwrap_message_dicts(messages: list[Any]) -> list[dict[str, Any]]:
    """Normalize SDK message dicts into ``{role, content}`` form.

    The Claude SDK wraps messages in ``{"message": {"role": ..., "content": ...}}``
    envelopes.  This function unwraps them into a flat list.
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            result.append(msg)
            continue
        if "message" in msg:
            inner = msg["message"]
            if isinstance(inner, dict):
                result.append(
                    {
                        "role": inner.get("role", "user"),
                        "content": inner.get("content", ""),
                    }
                )
            else:
                result.append(msg)
        else:
            result.append(msg)
    return result


def build_llm_input(prompt: Any, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Construct a combined prompt + history message list."""
    if isinstance(prompt, str):
        entry = {"content": prompt, "role": "user"}
        return [entry, *history] if history else [entry]

    if isinstance(prompt, list):
        formatted = unwrap_message_dicts(prompt)
        return [*formatted, *history] if history else formatted

    return list(history) if history else []
