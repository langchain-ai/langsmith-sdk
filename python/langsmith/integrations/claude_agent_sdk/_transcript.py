"""Transcript parsing for Claude Code subagent traces.

Reads JSONL transcript files and groups messages into turns for tracing.
Ported from the Claude Code CLI plugin.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


@dataclass
class ToolUseBlock:
    """A tool_use content block."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    """A tool_result content block."""

    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class TextBlock:
    """A text content block."""

    text: str


@dataclass
class ThinkingBlock:
    """A thinking content block."""

    thinking: str


ContentBlock = Union[TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock]


@dataclass
class ToolCall:
    """A tool call with its result."""

    tool_use: ToolUseBlock
    result: Optional[dict[str, Any]] = None
    agent_id: Optional[str] = None


@dataclass
class LLMCall:
    """A single LLM call within a turn."""

    content: list[ContentBlock]
    model: str
    usage: dict[str, int]
    start_time: str
    end_time: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    synthetic: bool = False


@dataclass
class Turn:
    """A turn in the conversation (user message + LLM calls)."""

    user_content: Union[str, list[dict[str, Any]]]
    user_timestamp: str
    llm_calls: list[LLMCall] = field(default_factory=list)
    is_complete: bool = True


def _strip_model_date_suffix(model: str) -> str:
    """Strip the date suffix from a model name.

    E.g. "claude-sonnet-4-5-20250929" -> "claude-sonnet-4-5"
    """
    import re

    return re.sub(r"-\d{8}$", "", model)


def _merge_adjacent_text_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Merge adjacent text blocks into one."""
    result: list[ContentBlock] = []
    text_buffer: Optional[str] = None

    for block in blocks:
        if isinstance(block, TextBlock):
            text_buffer = (text_buffer or "") + block.text
        else:
            if text_buffer is not None:
                result.append(TextBlock(text=text_buffer))
                text_buffer = None
            result.append(block)

    if text_buffer is not None:
        result.append(TextBlock(text=text_buffer))

    return result


def _parse_content_block(data: Any) -> ContentBlock:
    """Parse a content block from JSON."""
    if not isinstance(data, dict):
        return TextBlock(text=str(data))
    block_type = data.get("type")

    if block_type == "text":
        return TextBlock(text=data.get("text", ""))
    elif block_type == "thinking":
        return ThinkingBlock(thinking=data.get("thinking", ""))
    elif block_type == "tool_use":
        return ToolUseBlock(
            id=data.get("id", ""),
            name=data.get("name", ""),
            input=data.get("input", {}),
        )
    elif block_type == "tool_result":
        content = data.get("content", "")
        if isinstance(content, list):
            # Extract text from content array
            content = " ".join(
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        return ToolResultBlock(
            tool_use_id=data.get("tool_use_id", ""),
            content=str(content),
            is_error=data.get("is_error", False),
        )
    else:
        # Unknown block type, return as text
        return TextBlock(text=str(data))


def read_transcript(file_path: str) -> list[dict[str, Any]]:
    """Read a JSONL transcript file and return parsed messages.

    Returns an empty list on any I/O error (missing file, permission
    denied, etc.) so callers never need to handle filesystem exceptions.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return []

        messages = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue

        return messages
    except OSError:
        return []


def group_into_turns(messages: list[dict[str, Any]]) -> list[Turn]:
    """Group a flat list of transcript messages into turns.

    A turn starts with a human user message and includes all subsequent
    assistant messages and tool results.
    """
    turns: list[Turn] = []

    current_user: Optional[dict[str, Any]] = None
    current_prompt_id: Optional[str] = None
    assistant_chunks: dict[str, list[dict[str, Any]]] = {}
    assistant_order: list[str] = []
    tool_results: list[dict[str, Any]] = []
    has_stop_reason_end_turn = False

    def finalize_turn(force_incomplete: bool = False) -> None:
        nonlocal has_stop_reason_end_turn

        if current_user is None:
            return
        if not assistant_chunks:
            return

        # Check if turn is complete
        all_assistant = [m for chunks in assistant_chunks.values() for m in chunks]
        has_stop_reason_field = any(
            m.get("message", {}).get("stop_reason") is not None for m in all_assistant
        )
        is_complete = has_stop_reason_end_turn or (
            not force_incomplete and not has_stop_reason_field
        )

        llm_calls: list[LLMCall] = []

        for msg_id in assistant_order:
            chunks = assistant_chunks.get(msg_id, [])
            if not chunks:
                continue

            # Merge chunks
            first = chunks[0]
            last = chunks[-1]

            # Concatenate content blocks
            all_blocks: list[ContentBlock] = []
            for chunk in chunks:
                content_data = chunk.get("message", {}).get("content", [])
                if isinstance(content_data, list):
                    for block_data in content_data:
                        all_blocks.append(_parse_content_block(block_data))

            merged_blocks = _merge_adjacent_text_blocks(all_blocks)

            # Extract model and usage
            model = first.get("message", {}).get("model", "unknown")
            model = _strip_model_date_suffix(model)
            usage = last.get("message", {}).get("usage", {})

            # Extract timestamps
            start_time = first.get("timestamp", "")
            end_time = last.get("timestamp", "")

            # Extract tool uses and match with results
            tool_uses = [b for b in merged_blocks if isinstance(b, ToolUseBlock)]
            tool_calls: list[ToolCall] = []

            for tu in tool_uses:
                result = _find_tool_result(tu.id, tool_results)
                tool_calls.append(
                    ToolCall(
                        tool_use=tu,
                        result=result,
                        agent_id=result.get("agent_id") if result else None,
                    )
                )

            llm_calls.append(
                LLMCall(
                    content=merged_blocks,
                    model=model,
                    usage=usage,
                    start_time=start_time,
                    end_time=end_time,
                    tool_calls=tool_calls,
                )
            )

        user_content = current_user.get("message", {}).get("content", "")
        user_timestamp = current_user.get("timestamp", "")

        turns.append(
            Turn(
                user_content=user_content,
                user_timestamp=user_timestamp,
                llm_calls=llm_calls,
                is_complete=is_complete,
            )
        )

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type")

        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")

            # Human message: string content or array without tool_result
            is_human = isinstance(content, str) or (
                isinstance(content, list)
                and not any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in content
                )
            )

            if is_human:
                # Determine if this is a new turn
                prompt_id = msg.get("promptId")
                is_new_turn = (
                    current_user is None
                    or (prompt_id is not None and prompt_id != current_prompt_id)
                    or prompt_id is None
                )

                if is_new_turn:
                    finalize_turn()
                    current_prompt_id = prompt_id
                    current_user = msg
                    assistant_chunks = {}
                    assistant_order = []
                    tool_results = []
                    has_stop_reason_end_turn = False
            else:
                # Tool result message
                tool_results.append(msg)

        elif msg_type == "assistant":
            msg_id = msg.get("message", {}).get("id", "__no_id__")
            if msg_id not in assistant_chunks:
                assistant_chunks[msg_id] = []
                assistant_order.append(msg_id)
            assistant_chunks[msg_id].append(msg)

            # Check for end_turn
            if msg.get("message", {}).get("stop_reason") == "end_turn":
                has_stop_reason_end_turn = True

    # Finalize the last turn
    finalize_turn(force_incomplete=True)

    return turns


def _find_tool_result(
    tool_use_id: str, tool_results: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Find the tool result for a given tool_use_id."""
    for msg in tool_results:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                if block.get("tool_use_id") == tool_use_id:
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        result_content = " ".join(
                            c.get("text", "")
                            for c in result_content
                            if isinstance(c, dict) and c.get("type") == "text"
                        )
                    tool_use_result = msg.get("toolUseResult")
                    agent_id = (
                        tool_use_result.get("agentId")
                        if isinstance(tool_use_result, dict)
                        else None
                    )
                    return {
                        "content": str(result_content),
                        "timestamp": msg.get("timestamp", ""),
                        "agent_id": agent_id,
                    }
    return None
