"""Export ElevenLabs post-call traces to LangSmith.

ElevenLabs already emits a complete OTLP JSON trace for each conversation (the
``post_call_transcription_otel`` webhook). This module forwards that trace
unchanged and adds only what ElevenLabs does not provide: LangSmith run kinds,
the conversation messages, the thread id, the combined post-call audio
attachment, and the ``elevenlabs.*`` span attributes surfaced as run metadata.

The translation mirrors the streaming voice integrations (Pipecat, LiveKit) —
same ``langsmith.*`` / ``gen_ai.*`` namespaces, same root-span metadata, same
vendor-attribute pass-through, same size-capped audio attachment. It differs
only in operating on OTLP JSON dicts rather than live OTel spans.

Everything ElevenLabs sends is passed through untouched, so attributes this
module does not recognize (including ones ElevenLabs adds later) still reach
LangSmith rather than failing the export.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import json
import logging
import string
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import JsonValue

from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._beta_decorator import warn_beta
from langsmith.utils import LangSmithConflictError

if TYPE_CHECKING:
    from langsmith.async_client import AsyncClient
    from langsmith.client import Client

__all__ = [
    "DEFAULT_AUDIO_SIZE_LIMIT",
    "aexport_elevenlabs_trace",
    "export_elevenlabs_trace",
    "transform_elevenlabs_trace",
]

logger = logging.getLogger(__name__)

# Cap (bytes) on the decoded post-call audio, matching the streaming voice
# processors: the LangSmith ingester accepts attachments up to ~200MB and base64
# inflates by ~1.33x, so 150MB decoded encodes to ~200MB. ``None`` disables it.
DEFAULT_AUDIO_SIZE_LIMIT = 150_000_000
DEFAULT_MAX_SPANS = 10_000

_VENDOR_PREFIX = "elevenlabs."
_CONVERSATION_SPAN = "elevenlabs.conversation"
_TURN_SPAN_PREFIX = "elevenlabs.turn."
_TOOL_SPAN_PREFIX = "elevenlabs.tool."

# Per-turn token counts, keyed by model: ``elevenlabs.llm_usage.<model>.<field>``.
# The model name itself contains dots ("gemini-2.5-flash"), so the field is the
# last dot-separated component and the model is everything before it.
_LLM_USAGE_PREFIX = "elevenlabs.llm_usage."
_USAGE_OUTPUT = "output_total"
_USAGE_DETAILS = {
    "input_cache_read": "cache_read",
    "input_cache_write": "cache_creation",
}
_USAGE_INPUT_FIELDS = ("input", *_USAGE_DETAILS)
# Bounds ``literal_eval`` on vendor-supplied text.
_MAX_USAGE_LITERAL = 2048

# LangSmith reads ``ls_provider`` to attribute cost, so these are its slugs (the
# ones the other voice integrations and wrappers write), not OTel's gen_ai
# system names. Matched as substrings against the model, most specific first;
# an unrecognized model leaves the provider unset rather than guessing.
_MODEL_PROVIDERS = (
    ("claude", "anthropic"),
    ("gemini", "google"),
    ("gpt", "openai"),
    ("grok", "xai"),
    ("mixtral", "mistralai"),
    ("mistral", "mistralai"),
    ("deepseek", "deepseek"),
    ("command-r", "cohere"),
    ("llama", "meta"),
    ("qwen", "qwen"),
)
# OpenAI's reasoning models carry no vendor-identifying substring.
_OPENAI_PREFIXES = ("o1", "o3", "o4")

_CONVERSATION_ID_ATTR = "elevenlabs.conversation_id"
_AGENT_ID_ATTR = "elevenlabs.agent_id"
_PRODUCING_LLM_ATTR = "elevenlabs.producing_llm"
_USER_TEXT_ATTR = "elevenlabs.user.text"
_AGENT_TEXT_ATTR = "elevenlabs.agent.text"

# ElevenLabs documents that tool parameters and results are span attributes but
# never names the keys, so accept the plausible spellings and take the first hit.
_TOOL_INPUT_ATTRS = (
    "elevenlabs.tool.arguments",
    "elevenlabs.tool.parameters",
    "elevenlabs.tool.input",
)
_TOOL_OUTPUT_ATTRS = (
    "elevenlabs.tool.result",
    "elevenlabs.tool.output",
    "elevenlabs.tool.response",
)

# OTLP AnyValue members holding a single scalar, in the order they're probed.
_SCALAR_VALUE_KEYS = (
    "stringValue",
    "boolValue",
    "intValue",
    "doubleValue",
    "bytesValue",
)
_ATTACHMENT_NAME = "conversation_mp3"
_BASE64_CHARS = frozenset(string.ascii_letters + string.digits + "+/")


# -- OTLP JSON helpers --------------------------------------------------------


def _attributes(owner: Any) -> list[dict]:
    """Return a span/resource's attribute list, or ``[]`` when it has none."""
    attributes = owner.get("attributes") if isinstance(owner, Mapping) else None
    return attributes if isinstance(attributes, list) else []


def _scalar(attribute: Mapping) -> Optional[Any]:
    """Unwrap an OTLP ``AnyValue``'s scalar member (``None`` if absent)."""
    value = attribute.get("value")
    if not isinstance(value, Mapping):
        return None
    for key in _SCALAR_VALUE_KEYS:
        if key in value:
            return value[key]
    return None


def _get(attributes: Sequence[dict], *keys: str) -> Optional[Any]:
    """Return the value of the first of ``keys`` present in ``attributes``."""
    for key in keys:
        for attribute in attributes:
            if isinstance(attribute, Mapping) and attribute.get("key") == key:
                return _scalar(attribute)
    return None


def _any_value(value: Any) -> dict:
    """Wrap a Python scalar as an OTLP ``AnyValue`` (JSON-encoding anything else)."""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    return {"stringValue": json.dumps(value)}


def _set(span: dict, key: str, value: Any) -> None:
    """Set one attribute on a span, replacing any existing entry for ``key``."""
    attributes = span.get("attributes")
    if not isinstance(attributes, list):
        attributes = []
        span["attributes"] = attributes
    attribute = {"key": key, "value": _any_value(value)}
    for index, existing in enumerate(attributes):
        if isinstance(existing, Mapping) and existing.get("key") == key:
            attributes[index] = attribute
            return
    attributes.append(attribute)


def _set_metadata(span: dict, key: str, value: Any) -> None:
    """Set ``langsmith.metadata.<key>``, which LangSmith surfaces as run metadata."""
    _set(span, f"langsmith.metadata.{key}", value)


def _messages(role: str, content: Any) -> str:
    """Encode one message as the ``{"messages": [...]}`` blob LangSmith reads."""
    return json.dumps({"messages": [{"role": role, "content": content}]})


def _spans(payload: Mapping, max_spans: int) -> list[dict]:
    """Every span in the OTLP envelope, in document order."""
    spans = [
        span
        for resource_spans in payload.get("resourceSpans") or []
        for scope_spans in resource_spans.get("scopeSpans") or []
        for span in scope_spans.get("spans") or []
        if isinstance(span, dict)
    ]
    if not spans:
        raise ValueError("ElevenLabs OTLP trace contains no spans")
    if len(spans) > max_spans:
        raise ValueError(f"ElevenLabs OTLP trace exceeds the {max_spans} span limit")
    return spans


def _scope_version(payload: Mapping) -> Optional[str]:
    """Read the version ElevenLabs' own tracer stamps on what it produced.

    Their instrumentation scope (``elevenlabs.convai``) carries it, which is the
    honest answer for ``ls_integration_version``: the trace is built server-side,
    so the locally installed ``elevenlabs`` client — which this integration does
    not even require — says nothing about what produced it.
    """
    for resource_spans in payload.get("resourceSpans") or []:
        for scope_spans in resource_spans.get("scopeSpans") or []:
            scope = scope_spans.get("scope")
            version = scope.get("version") if isinstance(scope, Mapping) else None
            if isinstance(version, str) and version:
                return version
    return None


def _find(payload: Mapping, spans: Sequence[dict], key: str) -> Optional[str]:
    """Find ``key`` in the resource attributes, then in the spans."""
    for resource_spans in payload.get("resourceSpans") or []:
        value = _get(_attributes(resource_spans.get("resource")), key)
        if isinstance(value, str) and value:
            return value
    for span in spans:
        value = _get(_attributes(span), key)
        if isinstance(value, str) and value:
            return value
    return None


def _resolve(name: str, candidates: Sequence[Optional[str]]) -> Optional[str]:
    """Return the single id the payloads agree on, or ``None`` when none supplied.

    Disagreement is fatal: it means the caller correlated the audio webhook with
    a different conversation's trace, and attaching it would corrupt both runs.
    """
    values = {candidate for candidate in candidates if candidate}
    if len(values) > 1:
        raise ValueError(f"Mismatched {name} values in ElevenLabs payloads")
    return next(iter(values), None)


def _root(spans: Sequence[dict]) -> Optional[dict]:
    """Find the conversation root: the documented name, else the parentless span."""
    for span in spans:
        if span.get("name") == _CONVERSATION_SPAN:
            return span
    for span in spans:
        if not span.get("parentSpanId"):
            return span
    return None


# -- translation --------------------------------------------------------------


def _passthrough(span: dict) -> None:
    """Surface ``elevenlabs.*`` attributes as ``elevenlabs_*`` run metadata.

    Mirrors the ``lk.*`` pass-through in the LiveKit processor, and keeps the
    vendor's namespace distinct from LangSmith's own. Never clobbers metadata a
    branch already set, and skips non-scalars (nested OTLP array/kvlist values
    still reach LangSmith on the untouched original attribute).
    """
    for attribute in list(_attributes(span)):
        key = attribute.get("key")
        if not isinstance(key, str) or not key.startswith(_VENDOR_PREFIX):
            continue
        value = _scalar(attribute)
        if value is None:
            continue
        name = f"elevenlabs_{key[len(_VENDOR_PREFIX) :]}".replace(".", "_")
        if _get(_attributes(span), f"langsmith.metadata.{name}") is None:
            _set_metadata(span, name, value)


def _tokens(value: Any) -> Optional[int]:
    """Read a token count from an ``elevenlabs.llm_usage.*`` attribute.

    ElevenLabs sends these as a Python ``repr`` of a dict rather than JSON —
    ``"{'tokens': 2172, 'price': 0.0003258}"`` — so a plain ``int()`` or
    ``json.loads`` will not do. Falls back to ``literal_eval``, which evaluates
    literals only and never executes code, and accepts a bare number in case
    the shape changes.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str) or len(value) > _MAX_USAGE_LITERAL:
        return None
    try:
        parsed: Any = json.loads(value)
    except ValueError:
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return None
    if isinstance(parsed, Mapping):
        parsed = parsed.get("tokens")
    if isinstance(parsed, bool) or not isinstance(parsed, (int, float)):
        return None
    return int(parsed)


def _usage(span: dict, attributes: Sequence[dict]) -> set[str]:
    """Translate ``elevenlabs.llm_usage.*`` into LangSmith usage and model fields.

    ElevenLabs reports token counts per model on each agent-response span. This
    sums them into ``langsmith.usage_metadata`` so LangSmith shows real token
    counts and cost, and names the model on ``gen_ai.request.model``.
    """
    counts: dict[str, int] = {}
    models: set[str] = set()
    for attribute in attributes:
        key = attribute.get("key")
        if not isinstance(key, str) or not key.startswith(_LLM_USAGE_PREFIX):
            continue
        # The model name itself contains dots, so the field is the last component.
        model, _, field = key[len(_LLM_USAGE_PREFIX) :].rpartition(".")
        count = _tokens(_scalar(attribute))
        if not model or count is None:
            continue
        models.add(model)
        counts[field] = counts.get(field, 0) + count

    if not counts:
        return models
    # Cache reads are reported alongside ``input``, not inside it (one real turn
    # had input=692 with cache_read=1585), so the prompt total is their sum —
    # which also keeps the details a subset of ``input_tokens``.
    details = {
        name: counts[field]
        for field, name in _USAGE_DETAILS.items()
        if counts.get(field)
    }
    input_tokens = sum(counts.get(field, 0) for field in _USAGE_INPUT_FIELDS)
    output_tokens = counts.get(_USAGE_OUTPUT, 0)
    usage: dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    if details:
        usage["input_token_details"] = details
    _set(span, "langsmith.usage_metadata", json.dumps(usage))
    return models


def _provider(model: str) -> Optional[str]:
    """Resolve a model name to a LangSmith provider slug, if we recognize it."""
    lowered = model.lower()
    if lowered.startswith(_OPENAI_PREFIXES):
        return "openai"
    for fragment, provider in _MODEL_PROVIDERS:
        if fragment in lowered:
            return provider
    return None


def _model(span: dict, attributes: Sequence[dict], usage_models: set[str]) -> None:
    """Name the model and provider so LangSmith attributes tokens and cost.

    ElevenLabs names the model on the span directly; the ``llm_usage`` keys are
    the fallback, and only when the turn used exactly one model — otherwise any
    single choice would be wrong.
    """
    named = _get(attributes, _PRODUCING_LLM_ATTR)
    model = named if isinstance(named, str) and named else None
    if model is None and len(usage_models) == 1:
        model = next(iter(usage_models))
    if not model:
        return

    _set(span, "gen_ai.request.model", model)
    _set_metadata(span, "ls_model_name", model)
    provider = _provider(model)
    if provider:
        _set_metadata(span, "ls_provider", provider)
        # LangSmith maps either gen_ai provider key to ls_provider; writing both
        # is version-agnostic, as the streaming voice integrations do.
        _set(span, "gen_ai.provider.name", provider)
        _set(span, "gen_ai.system", provider)


def _translate(span: dict, thread_id: Optional[str]) -> None:
    """Add the LangSmith run kind, messages, and metadata for one span."""
    if thread_id:
        _set_metadata(span, "thread_id", thread_id)

    attributes = _attributes(span)
    name = span.get("name") or ""
    user_text = _get(attributes, _USER_TEXT_ATTR)
    agent_text = _get(attributes, _AGENT_TEXT_ATTR)

    if name == _CONVERSATION_SPAN:
        _set(span, "langsmith.span.kind", "chain")
    elif name.startswith(_TURN_SPAN_PREFIX):
        _set(span, "langsmith.span.kind", "chain")
        _set_metadata(span, "turn_number", name[len(_TURN_SPAN_PREFIX) :])
    elif name.startswith(_TOOL_SPAN_PREFIX):
        _set(span, "langsmith.span.kind", "tool")
        _set_metadata(span, "tool_name", name[len(_TOOL_SPAN_PREFIX) :])
        # Tool I/O is raw, not messages — the convention ``set_tool_input`` uses.
        if (value := _get(attributes, *_TOOL_INPUT_ATTRS)) is not None:
            _set(span, "gen_ai.prompt", value)
        if (value := _get(attributes, *_TOOL_OUTPUT_ATTRS)) is not None:
            _set(span, "gen_ai.completion", value)
    elif user_text is not None or agent_text is not None:
        # Keyed off the text attributes rather than the span name so this covers
        # both the ``recv.*`` post-call spans and the ``event.*`` monitoring ones.
        _set(span, "langsmith.span.kind", "llm")
        if user_text is not None:
            _set(span, "gen_ai.prompt", _messages("user", user_text))
        if agent_text is not None:
            _set(span, "gen_ai.completion", _messages("assistant", agent_text))

    _model(span, attributes, _usage(span, attributes))
    _passthrough(span)


# -- post-call audio ----------------------------------------------------------


def _audio_parts(
    audio: Any,
) -> tuple[Optional[str], int, Optional[str]]:
    """Normalize ``audio`` to ``(base64, decoded size, conversation id)``.

    Accepts raw MP3 bytes — what you get from ElevenLabs' conversations API —
    or a ``post_call_audio`` webhook payload, whose ``full_audio`` is already
    base64 and which also carries the conversation id for a sanity check.
    """
    if audio is None:
        return None, 0, None
    if isinstance(audio, (bytes, bytearray, memoryview)):
        raw = bytes(audio)
        if not raw:
            return None, 0, None
        return base64.b64encode(raw).decode("ascii"), len(raw), None
    if not isinstance(audio, Mapping):
        raise TypeError("audio must be bytes or a post_call_audio payload")

    data = audio.get("data", audio)
    if not isinstance(data, Mapping):
        raise ValueError("post_call_audio payload has no data object")
    conversation_id = data.get("conversation_id")
    conversation_id = conversation_id if isinstance(conversation_id, str) else None

    encoded = data.get("full_audio")
    if not isinstance(encoded, str) or not encoded:
        logger.warning(
            "langsmith elevenlabs: post_call_audio has no full_audio string; "
            "exporting the trace without the recording."
        )
        return None, 0, conversation_id
    size = _decoded_size(encoded)
    if size is None:
        logger.warning(
            "langsmith elevenlabs: post_call_audio.full_audio is not valid padded "
            "base64; exporting the trace without the recording."
        )
        return None, 0, conversation_id
    return encoded, size, conversation_id


def _decoded_size(encoded: str) -> Optional[int]:
    """Measure padded base64's decoded byte count, or ``None`` when it isn't valid.

    Computed arithmetically — the blob is forwarded base64-encoded, so it is
    never decoded in-process. Membership testing keeps this linear.
    """
    body = encoded.rstrip("=")
    padding = len(encoded) - len(body)
    if not encoded or len(encoded) % 4 or padding > 2:
        return None
    if not _BASE64_CHARS.issuperset(body):
        return None
    return len(encoded) // 4 * 3 - padding


def _attach_audio(
    root: dict, encoded: str, size: int, size_limit_bytes: Optional[int]
) -> bool:
    """Attach the combined MP3 to the root span via ``langsmith.attachments``.

    Honors ``size_limit_bytes`` and returns whether the audio was attached.
    Oversize audio is skipped with a warning rather than raised, so one
    unusable recording never costs the whole conversation trace.
    """
    if size_limit_bytes is not None and size > size_limit_bytes:
        logger.warning(
            "langsmith elevenlabs: post-call audio (%d bytes) exceeds "
            "audio_size_limit_bytes=%d; exporting the trace without the recording.",
            size,
            size_limit_bytes,
        )
        return False
    _set(
        root,
        "langsmith.attachments",
        json.dumps(
            [
                {
                    # LangSmith rejects attachment names containing periods.
                    "name": _ATTACHMENT_NAME,
                    "content": encoded,
                    "mime_type": "audio/mpeg",
                }
            ]
        ),
    )
    return True


# -- public API ---------------------------------------------------------------


@warn_beta
def transform_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    audio: Optional[Union[bytes, Mapping[str, JsonValue]]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
) -> dict[str, JsonValue]:
    """Add LangSmith voice fields to one ElevenLabs post-call OTLP trace.

    ``otlp_traces`` is the OTLP envelope itself — ``event["data"]["otlp_traces"]``
    from a ``post_call_transcription_otel`` webhook, or ``otlp_traces`` from the
    conversations API. ``audio`` is the conversation recording, either as raw
    MP3 bytes or as a ``post_call_audio`` webhook payload; omit it to export a
    trace with no recording.

    ElevenLabs' topology, timing, status, ids, and attributes are preserved, and
    the caller's payload is never mutated.
    """
    payload = deepcopy(dict(otlp_traces))
    spans = _spans(payload, max_spans)
    encoded, size, audio_conversation_id = _audio_parts(audio)

    conversation_id = _resolve(
        "conversation_id",
        [
            _find(payload, spans, _CONVERSATION_ID_ATTR),
            conversation_id,
            audio_conversation_id,
        ],
    )
    agent_id = _resolve("agent_id", [_find(payload, spans, _AGENT_ID_ATTR), agent_id])
    if not conversation_id:
        logger.warning(
            "langsmith elevenlabs: no conversation_id in the OTLP trace or the "
            "audio event; the trace will not be grouped into a thread."
        )

    for span in spans:
        _translate(span, conversation_id)

    root = _root(spans)
    if root is None:
        logger.warning(
            "langsmith elevenlabs: no %s root span; exporting without "
            "conversation-level metadata.",
            _CONVERSATION_SPAN,
        )
        return payload

    _set(root, "langsmith.root_span", True)
    _set_metadata(root, "ls_modality", "audio")
    _set_metadata(root, "ls_integration", "elevenlabs")
    _set_metadata(root, "ls_integration_version", _scope_version(payload) or "")
    # ElevenLabs' own trace id. LangSmith assigns its own run ids at ingest, so
    # without this there is no way back from a run to the conversation's trace on
    # their side (their API and monitoring socket share this id).
    trace_id = root.get("traceId")
    if isinstance(trace_id, str) and trace_id:
        _set_metadata(root, "elevenlabs_trace_id", trace_id)
    if conversation_id:
        _set_metadata(root, "conversation_id", conversation_id)
    if agent_id:
        _set_metadata(root, "agent_id", agent_id)
    if encoded is not None:
        _attach_audio(root, encoded, size, audio_size_limit_bytes)
    return payload


def _warn_duplicate() -> None:
    """Note a re-delivery. LangSmith rejects a repeat of a span it already has.

    ElevenLabs retries the transcript webhook, so the same conversation can
    arrive more than once. The trace is already in LangSmith, so this is a
    success for the caller rather than an error to handle.
    """
    logger.info(
        "langsmith elevenlabs: this conversation is already in LangSmith; "
        "treating the duplicate delivery as a no-op."
    )


def _project_name(project_name: Optional[str]) -> str:
    if project_name == "":
        raise ValueError("project_name must be a non-empty string")
    return project_name or ls_utils.get_tracer_project() or "default"


@warn_beta
def export_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    audio: Optional[Union[bytes, Mapping[str, JsonValue]]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
    client: Optional[Client] = None,
    project_name: Optional[str] = None,
) -> dict[str, JsonValue]:
    """Transform and synchronously export one ElevenLabs conversation trace."""
    from langsmith.client import Client

    payload = transform_elevenlabs_trace(
        otlp_traces,
        audio=audio,
        conversation_id=conversation_id,
        agent_id=agent_id,
        audio_size_limit_bytes=audio_size_limit_bytes,
        max_spans=max_spans,
    )
    owns_client = client is None
    resolved_client = client or Client()
    try:
        resolved_client.request_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            data=_orjson.dumps(payload),
            headers={"Langsmith-Project": _project_name(project_name)},
        )
    except LangSmithConflictError:
        _warn_duplicate()
    finally:
        if owns_client:
            resolved_client.close()
    return payload


@warn_beta
async def aexport_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    audio: Optional[Union[bytes, Mapping[str, JsonValue]]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
    client: Optional[AsyncClient] = None,
    project_name: Optional[str] = None,
) -> dict[str, JsonValue]:
    """Transform and asynchronously export one ElevenLabs conversation trace."""
    from langsmith.async_client import AsyncClient

    # Off the event loop: a post-call payload can carry a multi-megabyte audio
    # blob, and both the transform and the JSON encode are CPU-bound.
    payload = await asyncio.to_thread(
        lambda: transform_elevenlabs_trace(
            otlp_traces,
            audio=audio,
            conversation_id=conversation_id,
            agent_id=agent_id,
            audio_size_limit_bytes=audio_size_limit_bytes,
            max_spans=max_spans,
        )
    )
    body = await asyncio.to_thread(_orjson.dumps, payload)
    owns_client = client is None
    resolved_client = client or AsyncClient()
    try:
        await resolved_client._arequest_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            content=body,
            headers={"Langsmith-Project": _project_name(project_name)},
        )
    except LangSmithConflictError:
        _warn_duplicate()
    finally:
        if owns_client:
            await resolved_client.aclose()
    return payload
