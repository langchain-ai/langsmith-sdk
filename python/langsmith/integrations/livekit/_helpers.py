"""Small pure helpers for the LiveKit → LangSmith span processor.

Split out of :mod:`langsmith.integrations.livekit.processor` to keep that module
focused on span dispatch and lifecycle: provider-slug normalization, LiveKit
span detection, and the tiny chat-message builders the handlers reuse.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Optional

from langsmith._internal.voice._helpers import try_parse_json_object

logger = logging.getLogger(__name__)

# The instrumentation scope LiveKit's tracer is created under
# (``get_tracer("livekit-agents")``). Every span LiveKit emits carries it, so it
# is how we tell a LiveKit span apart from a non-LiveKit run riding the same OTel
# provider (e.g. a LangChain/LangGraph trace under ``LANGSMITH_TRACING_MODE=otel``).
_LIVEKIT_INSTRUMENTATION_SCOPE = "livekit-agents"

# LiveKit reports some providers as the API base-URL host (e.g. its OpenAI
# plugin → ``api.openai.com``), but LangSmith's cost engine keys on provider
# *slugs* (``openai`` / ``deepgram`` / …), so a hostname never matches a price.
# We recover the slug by substring — so ``beta.anthropic.com`` still → ``anthropic``
# — mirroring how LangSmith itself infers the provider from a model name.
_PROVIDER_ALIASES = (
    "openai",
    "anthropic",
    "gemini",
    "google",
    "deepgram",
    "cartesia",
    "elevenlabs",
    "cohere",
    "mistral",
    "groq",
)


def normalize_provider(raw: Any) -> Optional[str]:
    """Map a LiveKit provider (often an API host) to a LangSmith provider slug.

    Matches a known provider slug as a substring (so ``api.openai.com`` and
    ``beta.anthropic.com`` resolve to ``openai`` / ``anthropic``); otherwise
    returns the value's host, stripped of scheme/path. Returns ``None`` for
    empty input or LiveKit's ``"unknown"`` placeholder, so we never stamp a
    non-matching provider.
    """
    if not raw:
        return None
    value = str(raw).strip().lower()
    if not value or value == "unknown":
        return None
    for alias in _PROVIDER_ALIASES:
        if alias in value:
            return alias
    return value.split("://", 1)[-1].split("/", 1)[0] or None


def is_livekit_span(span: Any) -> bool:
    """Whether a span came from LiveKit's tracer (its instrumentation scope).

    Used to gate root detection: only a parentless span emitted by LiveKit is
    the conversation root. Named LiveKit spans are matched by name above and
    don't need this; it guards the broad ``parent is None`` case alone.
    """
    scope = getattr(span, "instrumentation_scope", None)
    return getattr(scope, "name", None) == _LIVEKIT_INSTRUMENTATION_SCOPE


def parse_tool_calls(raw_tool_calls: Any) -> list[dict]:
    """Parse an event's ``tool_calls`` to OpenAI-shape dicts (JSON strings decoded).

    Entries that are neither dicts nor JSON-object strings are dropped.
    """
    tool_calls: list[dict] = []
    for raw in raw_tool_calls or ():
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                continue
        if isinstance(raw, dict):
            tool_calls.append(raw)
    return tool_calls


def extract_provider_from_lk_metrics(metrics: Any) -> Optional[str]:
    """Read the provider (``metadata.model_provider``) from a LiveKit metrics blob.

    LiveKit reports it as the API-base-URL host (its OpenAI plugin →
    ``api.openai.com``); the caller normalizes it to a slug before setting it.
    """
    parsed = try_parse_json_object(metrics)
    if isinstance(parsed, dict):
        return (parsed.get("metadata") or {}).get("model_provider")
    return None


def extract_model_from_lk_metrics(metrics: Any) -> Optional[str]:
    """Read the model name (``metadata.model_name`` or ``model_name``) from a blob.

    LiveKit doesn't always set ``gen_ai.request.model`` (notably on ``tts_request``),
    so the model is recovered from the metrics blob as a fallback.
    """
    parsed = try_parse_json_object(metrics)
    if isinstance(parsed, dict):
        return (parsed.get("metadata") or {}).get("model_name") or parsed.get(
            "model_name"
        )
    return None


def _as_int(value: Any) -> Optional[int]:
    """Coerce a numeric metrics value to ``int``, or ``None`` if not numeric."""
    return int(value) if isinstance(value, (int, float)) else None


def extract_llm_usage(metrics: Any) -> dict[str, Any]:
    """Parse a ``lk.llm_metrics`` blob into ``set_usage`` kwargs."""
    parsed = try_parse_json_object(metrics)
    if not isinstance(parsed, dict):
        return {}
    usage: dict[str, Any] = {}
    if (v := _as_int(parsed.get("prompt_tokens"))) is not None:
        usage["input_tokens"] = v
    if (v := _as_int(parsed.get("completion_tokens"))) is not None:
        usage["output_tokens"] = v
    if (v := _as_int(parsed.get("total_tokens"))) is not None:
        usage["total_tokens"] = v
    if (v := _as_int(parsed.get("prompt_cached_tokens"))) is not None:
        usage["input_token_details"] = {"cache_read": v}
    return usage


def extract_realtime_usage(metrics: Any) -> dict[str, Any]:
    """Parse a ``lk.realtime_model_metrics`` blob into ``set_usage`` kwargs."""
    parsed = try_parse_json_object(metrics)
    if not isinstance(parsed, dict):
        return {}
    usage: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        if (count := _as_int(parsed.get(key))) is not None:
            usage[key] = count

    in_details = parsed.get("input_token_details")
    input_detail: dict[str, int] = {}
    if isinstance(in_details, dict):
        if (audio := _as_int(in_details.get("audio_tokens"))) is not None:
            input_detail["audio"] = audio
        if (cached := _as_int(in_details.get("cached_tokens"))) is not None:
            input_detail["cache_read"] = cached
    if input_detail:
        usage["input_token_details"] = input_detail

    out_details = parsed.get("output_token_details")
    if isinstance(out_details, dict):
        if (audio := _as_int(out_details.get("audio_tokens"))) is not None:
            usage["output_token_details"] = {"audio": audio}
    return usage


def flatten_lk_attributes_to_ls_metadata(
    obj: dict, prefix: str, _depth: int = 0
) -> dict:
    """Flatten a JSON-object blob's scalar leaves to ``{prefix_key: value}``.

    Recurses into nested dicts (capped at depth 4); keeps scalars and lists of
    scalars, dropping anything else. Returns a flat dict the caller stamps onto
    the span — so this stays agnostic to the span itself.
    """
    flat: dict = {}
    if _depth > 4:
        return flat
    for k, v in obj.items():
        name = f"{prefix}_{k}"
        if isinstance(v, dict):
            flat.update(flatten_lk_attributes_to_ls_metadata(v, name, _depth + 1))
        elif isinstance(v, (str, int, float, bool)):
            flat[name] = v
        elif (
            isinstance(v, (list, tuple))
            and v
            and all(isinstance(item, (str, int, float, bool)) for item in v)
        ):
            flat[name] = list(v)
    return flat


def build_tool_message(
    content: str,
    *,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """Build a ``tool`` result message, with its call id / name when present."""
    msg: dict = {"role": "tool", "content": content}
    if tool_call_id:
        msg["tool_call_id"] = str(tool_call_id)
    if name:
        msg["name"] = str(name)
    return msg


def build_message_from_event(role: str, event: Any) -> dict:
    """Build a chat message dict from a LiveKit ``gen_ai.*`` span event.

    ``role`` is authoritative (the caller derives it from the event name). Tool
    calls are forwarded in their OpenAI shape (JSON-string entries decoded) —
    LangSmith's ingester renders them directly.
    """
    attrs = event.attributes or {}
    content = str(attrs.get("content") or "")
    if role == "tool":
        return build_tool_message(
            content, tool_call_id=attrs.get("id"), name=attrs.get("name")
        )
    msg: dict = {"role": role, "content": content}
    tool_calls = parse_tool_calls(attrs.get("tool_calls"))
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


# ``system``/``developer`` items carry the agent's instructions, not conversation.
_TRANSCRIPT_SKIP_ROLES = {"system", "developer"}


def _content_to_text(content: Any) -> str:
    """Flatten a ``ChatMessage.content`` list to text, dropping non-text parts."""
    if isinstance(content, str):
        return content
    if not isinstance(content, (list, tuple)):
        return ""
    return "\n".join(part for part in content if isinstance(part, str))


def build_messages_from_chat_history(chat_history: Any) -> list[dict]:
    """Convert a LiveKit ``ChatContext`` into LangSmith chat messages.

    Keeps the conversation in ``created_at`` order — turns plus tool calls and
    their outputs — and drops the instructions and items with no message form.
    Returns ``[]`` for anything it can't read, so a malformed history degrades to
    the span-derived transcript rather than failing the export.
    """
    # ``to_dict`` has gained keywords over time (``strip_markup`` is newer than
    # our floor), so pass only the ones this version actually accepts rather
    # than risking a TypeError that would cost us the whole transcript.
    wanted = {
        "exclude_timestamp": False,  # we need created_at; the default drops it
        "exclude_function_call": False,  # tool calls belong in the transcript
        "exclude_metrics": True,
        "exclude_config_update": True,
        "strip_markup": True,
    }
    try:
        accepted = inspect.signature(chat_history.to_dict).parameters
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in accepted.values()):
            kwargs = dict(wanted)  # **kwargs absorbs whatever it doesn't name
        else:
            kwargs = {k: v for k, v in wanted.items() if k in accepted}
    except (TypeError, ValueError):  # pragma: no cover - exotic to_dict
        kwargs = {}

    try:
        payload = chat_history.to_dict(**kwargs)
    except Exception:
        logger.warning(
            "langsmith voice: could not read the session report's chat history; "
            "falling back to the transcript built from spans.",
            exc_info=True,
        )
        return []

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        logger.warning(
            "langsmith voice: session report chat history had no 'items'; "
            "falling back to the transcript built from spans."
        )
        return []

    ordered = sorted(items, key=lambda i: i.get("created_at") or 0.0)
    messages: list[dict] = []
    for item in ordered:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "message":
            role = item.get("role")
            if role in _TRANSCRIPT_SKIP_ROLES:
                continue
            text = _content_to_text(item.get("content"))
            if text:
                messages.append({"role": str(role or "user"), "content": text})
        elif kind == "function_call":
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": str(item.get("call_id") or ""),
                            "type": "function",
                            "function": {
                                "name": str(item.get("name") or ""),
                                "arguments": str(item.get("arguments") or ""),
                            },
                        }
                    ],
                }
            )
        elif kind == "function_call_output":
            messages.append(
                build_tool_message(
                    str(item.get("output") or ""),
                    tool_call_id=item.get("call_id"),
                    name=item.get("name"),
                )
            )
        # agent_handoff has no message equivalent; config updates are excluded.
    return messages
