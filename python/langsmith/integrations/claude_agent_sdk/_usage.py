"""Token usage utilities for Claude Agent SDK.

Normalizes raw Anthropic usage dicts into the canonical ``usage_metadata``
format expected by LangSmith.  The key Anthropic-specific behavior is that
cache tokens (``cache_read_input_tokens`` and ``cache_creation_input_tokens``)
are **additive** — they are *not* included in the raw ``input_tokens`` value,
so they must be summed in.

The canonical shape matches the JS LangSmith SDK's ``createUsageMetadata``:

.. code-block:: json

   {
     "input_tokens": 21400,
     "output_tokens": 7,
     "total_tokens": 21407,
     "input_token_details": {
       "cache_read": 21375,
       "ephemeral_5m_input_tokens": 0,
       "ephemeral_1hr_input_tokens": 0
     }
   }
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def extract_usage_metadata(usage: Any) -> dict[str, Any]:
    """Normalize a raw Anthropic usage dict into canonical ``usage_metadata``.

    Anthropic cache tokens are **additive**: ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` are not included in the raw
    ``input_tokens``, so we sum them in to get the true input total.
    """
    if not usage:
        return {}

    get = (
        usage.get if isinstance(usage, dict) else lambda k, d=None: getattr(usage, k, d)
    )

    raw_input = _to_int(get("input_tokens"))
    output_tokens = _to_int(get("output_tokens"))

    # Build input_token_details from cache fields
    input_token_details: dict[str, int] = {}

    cache_read = _to_int(get("cache_read_input_tokens"))
    if cache_read:
        input_token_details["cache_read"] = cache_read

    # Structured cache_creation (with ephemeral breakdown) takes precedence
    # over the flat cache_creation_input_tokens field.
    cache_creation = get("cache_creation")
    if isinstance(cache_creation, dict):
        eph_5m = _to_int(cache_creation.get("ephemeral_5m_input_tokens"))
        eph_1h = _to_int(cache_creation.get("ephemeral_1h_input_tokens"))
        if eph_5m:
            input_token_details["ephemeral_5m_input_tokens"] = eph_5m
        if eph_1h:
            input_token_details["ephemeral_1hr_input_tokens"] = eph_1h
    else:
        # Flat/legacy field — assume 5-minute cache
        flat_cache_create = _to_int(get("cache_creation_input_tokens"))
        if flat_cache_create:
            input_token_details["ephemeral_5m_input_tokens"] = flat_cache_create

    # Sum cache tokens into input_tokens (Anthropic cache tokens are additive)
    cache_token_sum = sum(input_token_details.values())
    adjusted_input = raw_input + cache_token_sum
    total_tokens = adjusted_input + output_tokens

    meta: dict[str, Any] = {
        "input_tokens": adjusted_input,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }
    if input_token_details:
        meta["input_token_details"] = input_token_details

    return meta


def read_usage_from_transcript(
    file_path: str,
) -> dict[str, dict[str, Any]]:
    """Read a JSONL transcript and return final usage per message_id.

    The Claude SDK streams assistant messages as multiple JSONL chunks
    with the same ``message.id``.  Only the final chunk (where
    ``stop_reason`` is set) has accurate ``output_tokens``.

    Returns:
        ``{message_id: usage_metadata}`` with canonical usage dicts.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {}

        # Collect the last usage seen per message_id — the final chunk
        # (with stop_reason set) overwrites earlier partials.
        raw_usage: dict[str, dict[str, Any]] = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if data.get("type") != "assistant":
                    continue
                msg = data.get("message", {})
                msg_id = msg.get("id")
                usage = msg.get("usage")
                if not msg_id or not usage:
                    continue
                # Always overwrite — later chunks have better counts.
                # The final chunk (with stop_reason) is last.
                raw_usage[msg_id] = usage

        return {mid: extract_usage_metadata(u) for mid, u in raw_usage.items() if u}
    except OSError as e:
        logger.debug(f"Could not read transcript {file_path}: {e}")
        return {}


def read_llm_turns_from_transcript(
    file_path: str,
) -> list[dict[str, Any]]:
    """Read final LLM turns from a JSONL transcript.

    Each API request produces two assistant entries in the transcript
    (a streaming partial and a final completion) sharing the same
    ``message.id``.  Only the **final** entry (with ``stop_reason`` set)
    is returned.

    Returns a list of dicts ordered by appearance, each containing::

        {
            "message_id": str,
            "model": str,
            "content": list[dict],  # Anthropic content blocks
            "stop_reason": str,  # "end_turn" or "tool_use"
            "usage": dict,  # raw Anthropic usage dict
            "timestamp": str | None,  # ISO 8601 timestamp
            "input_messages": list[dict],  # preceding conversation messages
        }
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return []

        # Single pass: build a running conversation history so each
        # assistant turn gets the full message context the API saw.
        # Tool result blocks are formatted as role:"tool" messages.
        entries_by_id: dict[str, dict[str, Any]] = {}
        conversation: list[dict[str, Any]] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                entry_type = data.get("type")

                if entry_type == "user":
                    msg = data.get("message", {})
                    content = msg.get("content")
                    if content is None:
                        continue
                    # Detect tool_result blocks and format as tool
                    # messages, matching the live stream formatting.
                    if isinstance(content, list) and content:
                        is_tool_result = any(
                            isinstance(b, dict) and b.get("type") == "tool_result"
                            for b in content
                        )
                        if is_tool_result:
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "tool_result"
                                ):
                                    conversation.append(
                                        {
                                            "role": "tool",
                                            "content": block.get("content", ""),
                                            "tool_call_id": block.get("tool_use_id"),
                                        }
                                    )
                            continue
                    conversation.append({"role": "user", "content": content})
                    continue

                if entry_type != "assistant":
                    continue

                msg = data.get("message", {})
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                # Always overwrite — the final entry (with stop_reason)
                # comes last for each message_id.
                entries_by_id[msg_id] = {
                    "message_id": msg_id,
                    "model": msg.get("model"),
                    "content": msg.get("content", []),
                    "stop_reason": msg.get("stop_reason"),
                    "usage": msg.get("usage"),
                    "timestamp": data.get("timestamp"),
                    # Full conversation history up to this turn.
                    "input_messages": list(conversation),
                }
                # Add completed assistant content to conversation
                # so subsequent turns see it.
                if msg.get("stop_reason"):
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": msg.get("content", []),
                        }
                    )

        # Only return final entries (stop_reason is set).
        return [e for e in entries_by_id.values() if e.get("stop_reason")]
    except OSError as e:
        logger.debug(f"Could not read transcript {file_path}: {e}")
        return []
