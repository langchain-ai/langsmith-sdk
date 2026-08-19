"""Transform and export ElevenLabs post-call OpenTelemetry traces.

ElevenLabs emits one complete OTLP JSON trace for each conversation, while its
combined MP3 recording arrives in a separate ``post_call_audio`` webhook.  This
module keeps webhook receipt and correlation in the application and provides a
stateless bridge that:

* preserves ElevenLabs' trace topology and timing;
* adds the LangSmith attributes used by the voice-trace UI;
* attaches the combined MP3 to the conversation root; and
* forwards the resulting OTLP JSON through the existing LangSmith clients.

The bridge deliberately does not fetch files, retain unmatched webhook state,
or verify ElevenLabs webhook signatures.  Applications should verify and
durably correlate both webhook events by ``conversation_id`` before calling it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langsmith import utils as ls_utils
from langsmith._internal import _orjson
from langsmith._internal._beta_decorator import warn_beta

if TYPE_CHECKING:
    import httpx
    import requests

    from langsmith.async_client import AsyncClient
    from langsmith.client import Client

__all__ = [
    "DEFAULT_AUDIO_SIZE_LIMIT",
    "aexport_elevenlabs_trace",
    "export_elevenlabs_trace",
    "transform_elevenlabs_trace",
]

# Match the existing voice integrations' attachment cap without importing their
# OpenTelemetry-dependent span processor. This bridge handles serialized OTLP
# and intentionally works with the base ``langsmith`` installation.
DEFAULT_AUDIO_SIZE_LIMIT = 150_000_000
DEFAULT_MAX_SPANS = 10_000

_TRACE_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_SPAN_ID_RE = re.compile(r"^[0-9a-fA-F]{16}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")

_CONVERSATION_SPAN = "elevenlabs.conversation"
_USER_TRANSCRIPT_SPAN = "elevenlabs.recv.user_transcript"
_AGENT_RESPONSE_SPAN = "elevenlabs.recv.agent_response"
_TOOL_SPAN_PREFIX = "elevenlabs.tool."

_CONVERSATION_ID_ATTR = "elevenlabs.conversation_id"
_AGENT_ID_ATTR = "elevenlabs.agent_id"
_SOURCE_ATTR = "elevenlabs.source"
_USER_TEXT_ATTR = "elevenlabs.user.text"
_AGENT_TEXT_ATTR = "elevenlabs.agent.text"

_TOOL_INPUT_SUFFIXES = frozenset({"arguments", "input", "parameters", "request"})
_TOOL_OUTPUT_SUFFIXES = frozenset({"output", "response", "result"})


class _OtlpEnvelope(BaseModel):
    """Strictly validate the OTLP request envelope before walking it."""

    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    resource_spans: list[dict[str, Any]] = Field(alias="resourceSpans")


class _PostCallAudioData(BaseModel):
    """The documented data object for ``post_call_audio``."""

    model_config = ConfigDict(strict=True, extra="ignore")

    agent_id: str
    conversation_id: str
    full_audio: str = Field(repr=False)


class _PostCallAudioEvent(BaseModel):
    """The documented outer ``post_call_audio`` webhook envelope."""

    model_config = ConfigDict(strict=True, extra="ignore")

    type: Literal["post_call_audio"]
    data: _PostCallAudioData
    event_timestamp: Optional[int] = None


@dataclass
class _SpanRef:
    span: dict[str, Any]
    resource_attributes: list[dict[str, Any]]
    order: int


def _sanitized_validation_error(message: str, error: ValidationError) -> ValueError:
    """Return a validation error without echoing sensitive input values."""
    return ValueError(f"{message} ({error.error_count()} validation errors)")


def _validated_otlp_copy(otlp_traces: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(otlp_traces, Mapping):
        raise TypeError("otlp_traces must be a mapping containing resourceSpans")
    try:
        envelope = _OtlpEnvelope.model_validate(dict(otlp_traces))
    except ValidationError as error:
        raise _sanitized_validation_error(
            "Invalid OTLP trace envelope", error
        ) from None
    return envelope.model_dump(by_alias=True)


def _parse_audio(
    post_call_audio: Optional[Mapping[str, Any]],
) -> Optional[_PostCallAudioData]:
    if post_call_audio is None:
        return None
    if not isinstance(post_call_audio, Mapping):
        raise TypeError("post_call_audio must be a parsed webhook or data mapping")
    try:
        if "data" in post_call_audio:
            return _PostCallAudioEvent.model_validate(dict(post_call_audio)).data
        return _PostCallAudioData.model_validate(dict(post_call_audio))
    except ValidationError as error:
        raise _sanitized_validation_error(
            "Invalid ElevenLabs post_call_audio payload", error
        ) from None


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list")
    return value


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _attributes(container: dict[str, Any], path: str) -> list[dict[str, Any]]:
    raw = container.setdefault("attributes", [])
    attrs = _require_list(raw, f"{path}.attributes")
    result: list[dict[str, Any]] = []
    for index, attribute in enumerate(attrs):
        result.append(_require_dict(attribute, f"{path}.attributes[{index}]"))
    return result


def _collect_spans(payload: dict[str, Any], max_spans: int) -> list[_SpanRef]:
    if not isinstance(max_spans, int) or isinstance(max_spans, bool) or max_spans < 1:
        raise ValueError("max_spans must be a positive integer")

    refs: list[_SpanRef] = []
    resource_spans = _require_list(payload.get("resourceSpans"), "resourceSpans")
    for resource_index, resource_span_raw in enumerate(resource_spans):
        resource_span = _require_dict(
            resource_span_raw, f"resourceSpans[{resource_index}]"
        )
        resource = _require_dict(
            resource_span.get("resource", {}),
            f"resourceSpans[{resource_index}].resource",
        )
        resource_attrs = _attributes(
            resource, f"resourceSpans[{resource_index}].resource"
        )
        scope_spans = _require_list(
            resource_span.get("scopeSpans"),
            f"resourceSpans[{resource_index}].scopeSpans",
        )
        for scope_index, scope_span_raw in enumerate(scope_spans):
            scope_span = _require_dict(
                scope_span_raw,
                f"resourceSpans[{resource_index}].scopeSpans[{scope_index}]",
            )
            spans = _require_list(
                scope_span.get("spans"),
                f"resourceSpans[{resource_index}].scopeSpans[{scope_index}].spans",
            )
            for span_index, span_raw in enumerate(spans):
                if len(refs) >= max_spans:
                    raise ValueError(f"OTLP trace exceeds the {max_spans} span limit")
                span = _require_dict(
                    span_raw,
                    "resourceSpans"
                    f"[{resource_index}].scopeSpans[{scope_index}].spans[{span_index}]",
                )
                _attributes(span, f"span[{len(refs)}]")
                refs.append(_SpanRef(span, resource_attrs, len(refs)))

    if not refs:
        raise ValueError("OTLP trace must contain at least one span")
    return refs


def _decode_any_value(value: Any, path: str) -> Any:
    value = _require_dict(value, path)
    if len(value) != 1:
        raise ValueError(f"{path} must contain exactly one OTLP AnyValue field")
    kind, raw = next(iter(value.items()))
    if kind == "stringValue":
        if not isinstance(raw, str):
            raise ValueError(f"{path}.stringValue must be a string")
        return raw
    if kind == "boolValue":
        if not isinstance(raw, bool):
            raise ValueError(f"{path}.boolValue must be a boolean")
        return raw
    if kind == "intValue":
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise ValueError(f"{path}.intValue must be an integer or decimal string")
        if isinstance(raw, str) and not re.fullmatch(r"-?[0-9]+", raw):
            raise ValueError(f"{path}.intValue must be a decimal string")
        return int(raw)
    if kind == "doubleValue":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{path}.doubleValue must be numeric")
        return float(raw)
    if kind == "bytesValue":
        if not isinstance(raw, str):
            raise ValueError(f"{path}.bytesValue must be a base64 string")
        return raw
    if kind == "arrayValue":
        array = _require_dict(raw, f"{path}.arrayValue")
        values = _require_list(array.get("values", []), f"{path}.arrayValue.values")
        return [
            _decode_any_value(item, f"{path}.arrayValue.values[{index}]")
            for index, item in enumerate(values)
        ]
    if kind == "kvlistValue":
        kvlist = _require_dict(raw, f"{path}.kvlistValue")
        values = _require_list(kvlist.get("values", []), f"{path}.kvlistValue.values")
        result: dict[str, Any] = {}
        for index, item_raw in enumerate(values):
            item = _require_dict(item_raw, f"{path}.kvlistValue.values[{index}]")
            key = item.get("key")
            if not isinstance(key, str):
                raise ValueError(f"{path}.kvlistValue.values[{index}].key is invalid")
            result[key] = _decode_any_value(
                item.get("value"), f"{path}.kvlistValue.values[{index}].value"
            )
        return result
    raise ValueError(f"{path} uses unsupported OTLP AnyValue field {kind!r}")


def _attribute_values(attrs: list[dict[str, Any]], key: str, path: str) -> list[Any]:
    values: list[Any] = []
    for index, attribute in enumerate(attrs):
        attribute_key = attribute.get("key")
        if not isinstance(attribute_key, str):
            raise ValueError(f"{path}[{index}].key must be a string")
        if "value" not in attribute:
            raise ValueError(f"{path}[{index}].value is required")
        decoded = _decode_any_value(attribute["value"], f"{path}[{index}].value")
        if attribute_key == key:
            values.append(decoded)
    return values


def _attributes_dict(attrs: list[dict[str, Any]], path: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index, attribute in enumerate(attrs):
        key = attribute.get("key")
        if not isinstance(key, str):
            raise ValueError(f"{path}[{index}].key must be a string")
        result[key] = _decode_any_value(
            attribute.get("value"), f"{path}[{index}].value"
        )
    return result


def _encode_any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": _orjson.dumps(value).decode("utf-8")}


def _set_attribute(attrs: list[dict[str, Any]], key: str, value: Any) -> None:
    encoded = _encode_any_value(value)
    for attribute in attrs:
        if attribute.get("key") == key:
            attribute["value"] = encoded
            return
    attrs.append({"key": key, "value": encoded})


def _resolve_identifier(name: str, candidates: list[Any], required: bool) -> str | None:
    normalized: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        if not isinstance(candidate, str) or not candidate:
            raise ValueError(f"{name} must be a non-empty string")
        normalized.add(candidate)
    if len(normalized) > 1:
        raise ValueError(f"Mismatched {name} values in ElevenLabs payloads")
    if not normalized:
        if required:
            raise ValueError(f"ElevenLabs OTLP trace is missing {name}")
        return None
    return next(iter(normalized))


def _validate_identity(refs: list[_SpanRef]) -> tuple[str, _SpanRef]:
    trace_ids: set[str] = set()
    span_ids: set[str] = set()
    roots: list[_SpanRef] = []
    for ref in refs:
        name = ref.span.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Every OTLP span must have a non-empty name")
        trace_id = ref.span.get("traceId")
        span_id = ref.span.get("spanId")
        parent_span_id = ref.span.get("parentSpanId")
        if not isinstance(trace_id, str) or not _TRACE_ID_RE.fullmatch(trace_id):
            raise ValueError("Every OTLP span must have a 32-character hex traceId")
        if not isinstance(span_id, str) or not _SPAN_ID_RE.fullmatch(span_id):
            raise ValueError("Every OTLP span must have a 16-character hex spanId")
        if parent_span_id not in (None, "") and (
            not isinstance(parent_span_id, str)
            or not _SPAN_ID_RE.fullmatch(parent_span_id)
        ):
            raise ValueError("OTLP parentSpanId must be a 16-character hex value")
        normalized_span_id = span_id.lower()
        if normalized_span_id in span_ids:
            raise ValueError("OTLP trace contains duplicate spanId values")
        trace_ids.add(trace_id.lower())
        span_ids.add(normalized_span_id)
        if name == _CONVERSATION_SPAN:
            roots.append(ref)

    if len(trace_ids) != 1:
        raise ValueError("An ElevenLabs conversation must contain exactly one traceId")
    if len(roots) != 1:
        raise ValueError(
            "An ElevenLabs conversation must contain exactly one "
            "elevenlabs.conversation root span"
        )
    if roots[0].span.get("parentSpanId") not in (None, ""):
        raise ValueError("The elevenlabs.conversation root span cannot have a parent")
    return next(iter(trace_ids)), roots[0]


def _identifier_candidates(refs: list[_SpanRef], key: str) -> list[Any]:
    candidates: list[Any] = []
    seen_resources: set[int] = set()
    for ref in refs:
        resource_id = id(ref.resource_attributes)
        if resource_id not in seen_resources:
            seen_resources.add(resource_id)
            candidates.extend(
                _attribute_values(ref.resource_attributes, key, "resource.attributes")
            )
        span_attrs = cast(list[dict[str, Any]], ref.span["attributes"])
        candidates.extend(_attribute_values(span_attrs, key, "span.attributes"))
    return candidates


def _span_start(ref: _SpanRef) -> tuple[int, int]:
    raw = ref.span.get("startTimeUnixNano")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw, ref.order
    if isinstance(raw, str) and raw.isdigit():
        return int(raw), ref.order
    return 0, ref.order


def _message_json(messages: list[dict[str, str]]) -> str:
    return _orjson.dumps({"messages": messages}).decode("utf-8")


def _tool_io(attrs: dict[str, Any], suffixes: frozenset[str]) -> Any:
    matches = {
        key: value
        for key, value in attrs.items()
        if key.startswith("elevenlabs.tool.") and key.rsplit(".", 1)[-1] in suffixes
    }
    if len(matches) == 1:
        return next(iter(matches.values()))
    return matches or None


def _io_json(value: Any) -> str:
    return value if isinstance(value, str) else _orjson.dumps(value).decode("utf-8")


def _validate_audio_base64(value: str, size_limit_bytes: Optional[int]) -> int:
    if not value or len(value) % 4 != 0 or not _BASE64_RE.fullmatch(value):
        raise ValueError("post_call_audio.full_audio is not valid padded base64")
    padding = len(value) - len(value.rstrip("="))
    decoded_size = (len(value) // 4) * 3 - padding
    if size_limit_bytes is not None:
        if (
            not isinstance(size_limit_bytes, int)
            or isinstance(size_limit_bytes, bool)
            or size_limit_bytes < 0
        ):
            raise ValueError("audio_size_limit_bytes must be non-negative or None")
        if decoded_size > size_limit_bytes:
            raise ValueError(
                "ElevenLabs post-call audio exceeds the configured decoded-byte limit"
            )
    return decoded_size


def _topology(refs: list[_SpanRef]) -> list[tuple[str, str, str, str]]:
    return sorted(
        (
            ref.span["traceId"],
            ref.span["spanId"],
            ref.span.get("parentSpanId", ""),
            ref.span["name"],
        )
        for ref in refs
    )


def _apply_anonymizer(
    payload: dict[str, Any],
    anonymizer: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    max_spans: int,
    conversation_id: str,
) -> dict[str, Any]:
    before_refs = _collect_spans(payload, max_spans)
    before_topology = _topology(before_refs)
    anonymized = anonymizer(payload)
    if not isinstance(anonymized, dict):
        raise ValueError("anonymizer must return an OTLP mapping")
    after_refs = _collect_spans(anonymized, max_spans)
    if _topology(after_refs) != before_topology:
        raise ValueError("anonymizer cannot modify OTLP trace topology or identities")
    after_conversation_id = _resolve_identifier(
        "conversation_id",
        _identifier_candidates(after_refs, _CONVERSATION_ID_ATTR),
        required=True,
    )
    if after_conversation_id != conversation_id:
        raise ValueError("anonymizer cannot modify the ElevenLabs conversation_id")
    return anonymized


def transform_elevenlabs_trace(
    otlp_traces: Mapping[str, Any],
    *,
    post_call_audio: Optional[Mapping[str, Any]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    anonymizer: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
) -> dict[str, Any]:
    """Build one LangSmith-ready OTLP trace from ElevenLabs post-call data.

    Args:
        otlp_traces: The ``data.otlp_traces`` object from an ElevenLabs
            ``post_call_transcription_otel`` webhook or conversation GET response.
        post_call_audio: The parsed ``post_call_audio`` webhook, or its ``data``
            object. The combined MP3 is attached to the conversation root.
        conversation_id: Optional trusted conversation ID. If provided, it must
            match the IDs embedded in the OTLP and audio payloads.
        agent_id: Optional trusted agent ID. If provided, it must match payloads.
        metadata: Additional allowlisted metadata to stamp on every span.
        anonymizer: Optional LangSmith-compatible anonymizer applied before audio
            attachment. It must preserve trace/span and conversation identities.
        audio_size_limit_bytes: Maximum decoded MP3 size. ``None`` disables the
            limit. Oversized audio is rejected, never truncated.
        max_spans: Maximum number of spans accepted for one conversation.

    Returns:
        A new OTLP JSON dictionary. The caller's inputs are not mutated.
    """
    payload = _validated_otlp_copy(otlp_traces)
    refs = _collect_spans(payload, max_spans)
    _trace_id, root = _validate_identity(refs)
    audio = _parse_audio(post_call_audio)

    resolved_conversation_id = _resolve_identifier(
        "conversation_id",
        [
            *_identifier_candidates(refs, _CONVERSATION_ID_ATTR),
            conversation_id,
            audio.conversation_id if audio else None,
        ],
        required=True,
    )
    assert resolved_conversation_id is not None
    resolved_agent_id = _resolve_identifier(
        "agent_id",
        [
            *_identifier_candidates(refs, _AGENT_ID_ATTR),
            agent_id,
            audio.agent_id if audio else None,
        ],
        required=False,
    )
    resolved_source = _resolve_identifier(
        "source",
        _identifier_candidates(refs, _SOURCE_ATTR),
        required=False,
    )

    safe_metadata: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if not isinstance(key, str) or not key or key.startswith("langsmith."):
            raise ValueError(
                "metadata keys must be non-empty strings outside langsmith.*"
            )
        safe_metadata[key] = value

    ordered_refs = sorted(refs, key=_span_start)
    transcript: list[dict[str, str]] = []
    history: list[dict[str, str]] = []
    for ref in refs:
        attrs = cast(list[dict[str, Any]], ref.span["attributes"])
        _set_attribute(attrs, "langsmith.metadata.thread_id", resolved_conversation_id)
        _set_attribute(
            attrs,
            "langsmith.metadata.elevenlabs_conversation_id",
            resolved_conversation_id,
        )
        _set_attribute(attrs, "langsmith.metadata.ls_integration", "elevenlabs")
        if resolved_agent_id:
            _set_attribute(
                attrs, "langsmith.metadata.elevenlabs_agent_id", resolved_agent_id
            )
        if resolved_source:
            _set_attribute(
                attrs, "langsmith.metadata.elevenlabs_source", resolved_source
            )
        for key, value in safe_metadata.items():
            _set_attribute(attrs, f"langsmith.metadata.{key}", value)

    for ref in ordered_refs:
        span = ref.span
        attrs = cast(list[dict[str, Any]], span["attributes"])
        decoded = _attributes_dict(attrs, "span.attributes")
        name = cast(str, span["name"])
        if name == _USER_TRANSCRIPT_SPAN:
            text = decoded.get(_USER_TEXT_ATTR)
            _set_attribute(attrs, "langsmith.span.kind", "llm")
            if isinstance(text, str) and text.strip():
                message = {"role": "user", "content": text.strip()}
                _set_attribute(attrs, "gen_ai.prompt", _message_json([message]))
                transcript.append(message)
                history.append(message)
        elif name == _AGENT_RESPONSE_SPAN:
            text = decoded.get(_AGENT_TEXT_ATTR)
            _set_attribute(attrs, "langsmith.span.kind", "llm")
            if history:
                _set_attribute(attrs, "gen_ai.prompt", _message_json(history))
            if isinstance(text, str) and text.strip():
                message = {"role": "assistant", "content": text.strip()}
                _set_attribute(attrs, "gen_ai.completion", _message_json([message]))
                transcript.append(message)
                history.append(message)
        elif name.startswith(_TOOL_SPAN_PREFIX):
            _set_attribute(attrs, "langsmith.span.kind", "tool")
            tool_input = _tool_io(decoded, _TOOL_INPUT_SUFFIXES)
            tool_output = _tool_io(decoded, _TOOL_OUTPUT_SUFFIXES)
            if tool_input is not None:
                _set_attribute(attrs, "gen_ai.prompt", _io_json(tool_input))
            if tool_output is not None:
                _set_attribute(attrs, "gen_ai.completion", _io_json(tool_output))

    root_attrs = cast(list[dict[str, Any]], root.span["attributes"])
    _set_attribute(root_attrs, "langsmith.span.kind", "chain")
    _set_attribute(root_attrs, "langsmith.root_span", True)
    _set_attribute(root_attrs, "langsmith.metadata.ls_modality", "audio")
    _set_attribute(root_attrs, "langsmith.span.tags", "elevenlabs, voice")
    if transcript:
        _set_attribute(root_attrs, "gen_ai.prompt", _message_json(transcript))

    if anonymizer is not None:
        payload = _apply_anonymizer(
            payload,
            anonymizer,
            max_spans=max_spans,
            conversation_id=resolved_conversation_id,
        )
        refs = _collect_spans(payload, max_spans)
        _, root = _validate_identity(refs)
        root_attrs = cast(list[dict[str, Any]], root.span["attributes"])
        # The anonymizer may replace arbitrary strings. Reassert structural
        # LangSmith attributes after validating that the OTLP topology and
        # ElevenLabs conversation identity are unchanged.
        for ref in refs:
            attrs = cast(list[dict[str, Any]], ref.span["attributes"])
            _set_attribute(
                attrs, "langsmith.metadata.thread_id", resolved_conversation_id
            )
            _set_attribute(
                attrs,
                "langsmith.metadata.elevenlabs_conversation_id",
                resolved_conversation_id,
            )
            name = cast(str, ref.span["name"])
            if name in {_USER_TRANSCRIPT_SPAN, _AGENT_RESPONSE_SPAN}:
                _set_attribute(attrs, "langsmith.span.kind", "llm")
            elif name.startswith(_TOOL_SPAN_PREFIX):
                _set_attribute(attrs, "langsmith.span.kind", "tool")
        _set_attribute(root_attrs, "langsmith.span.kind", "chain")
        _set_attribute(root_attrs, "langsmith.root_span", True)
        _set_attribute(root_attrs, "langsmith.metadata.ls_modality", "audio")
        _set_attribute(root_attrs, "langsmith.span.tags", "elevenlabs, voice")

    if audio is not None:
        _validate_audio_base64(audio.full_audio, audio_size_limit_bytes)
        attachment = json.dumps(
            [
                {
                    "name": "conversation.mp3",
                    "content": audio.full_audio,
                    "mime_type": "audio/mpeg",
                }
            ],
            separators=(",", ":"),
        )
        _set_attribute(root_attrs, "langsmith.attachments", attachment)

    return payload


def _project_name(project_name: Optional[str]) -> str:
    if project_name is not None and (
        not isinstance(project_name, str) or not project_name
    ):
        raise ValueError("project_name must be a non-empty string")
    return project_name or ls_utils.get_tracer_project() or "default"


@warn_beta
def export_elevenlabs_trace(
    otlp_traces: Mapping[str, Any],
    *,
    post_call_audio: Optional[Mapping[str, Any]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    anonymizer: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
    client: Optional[Client] = None,
    project_name: Optional[str] = None,
) -> dict[str, Any]:
    """Transform and synchronously export one ElevenLabs conversation trace."""
    from langsmith.client import Client

    payload = transform_elevenlabs_trace(
        otlp_traces,
        post_call_audio=post_call_audio,
        conversation_id=conversation_id,
        agent_id=agent_id,
        metadata=metadata,
        anonymizer=anonymizer,
        audio_size_limit_bytes=audio_size_limit_bytes,
        max_spans=max_spans,
    )
    body = _orjson.dumps(payload)
    owns_client = client is None
    resolved_client = client or Client()
    try:
        response: requests.Response = resolved_client.request_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            data=body,
            headers={"Langsmith-Project": _project_name(project_name)},
        )
        del response
    finally:
        if owns_client:
            resolved_client.close()
    return payload


@warn_beta
async def aexport_elevenlabs_trace(
    otlp_traces: Mapping[str, Any],
    *,
    post_call_audio: Optional[Mapping[str, Any]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    anonymizer: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
    client: Optional[AsyncClient] = None,
    project_name: Optional[str] = None,
) -> dict[str, Any]:
    """Transform and asynchronously export one ElevenLabs conversation trace."""
    from langsmith.async_client import AsyncClient

    payload = transform_elevenlabs_trace(
        otlp_traces,
        post_call_audio=post_call_audio,
        conversation_id=conversation_id,
        agent_id=agent_id,
        metadata=metadata,
        anonymizer=anonymizer,
        audio_size_limit_bytes=audio_size_limit_bytes,
        max_spans=max_spans,
    )
    body = _orjson.dumps(payload)
    owns_client = client is None
    resolved_client = client or AsyncClient()
    try:
        response: httpx.Response = await resolved_client._arequest_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            content=body,
            headers={"Langsmith-Project": _project_name(project_name)},
        )
        del response
    finally:
        if owns_client:
            await resolved_client.aclose()
    return payload
