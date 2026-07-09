"""Small pure helpers for the LiveKit → LangSmith span processor.

Split out of :mod:`langsmith.integrations.livekit.processor` to keep that module
focused on span dispatch and lifecycle: provider-slug normalization, LiveKit
span detection, and the tiny chat-message builders the handlers reuse.
"""

from __future__ import annotations

import json
from typing import Any, Optional

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


def build_user_message(content: str) -> dict:
    """Build a ``user`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "user", "content": content}


def build_assistant_message(content: str) -> dict:
    """Build an ``assistant`` chat message for the ``gen_ai.*`` message keys."""
    return {"role": "assistant", "content": content}


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
