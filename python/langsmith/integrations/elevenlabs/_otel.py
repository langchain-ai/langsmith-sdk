"""Export ElevenLabs post-call traces to LangSmith.

ElevenLabs already emits a complete OTLP JSON trace for each conversation. This
module preserves that trace and adds only the LangSmith fields that ElevenLabs
does not provide: voice metadata, the combined post-call audio attachment, and
message/run-type attributes used by LangSmith's trace UI.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

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
_USER_TEXT_ATTR = "elevenlabs.user.text"
_AGENT_TEXT_ATTR = "elevenlabs.agent.text"


class _StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)


class _AnyValue(_StrictModel):
    """OTLP JSON AnyValue."""

    string_value: Optional[StrictStr] = Field(default=None, alias="stringValue")
    bool_value: Optional[StrictBool] = Field(default=None, alias="boolValue")
    int_value: Optional[StrictInt | StrictStr] = Field(default=None, alias="intValue")
    double_value: Optional[StrictFloat] = Field(default=None, alias="doubleValue")
    bytes_value: Optional[StrictStr] = Field(default=None, alias="bytesValue")
    array_value: Optional[_ArrayValue] = Field(default=None, alias="arrayValue")
    kvlist_value: Optional[_KeyValueList] = Field(default=None, alias="kvlistValue")

    @model_validator(mode="after")
    def _exactly_one_value(self) -> _AnyValue:
        values = (
            self.string_value,
            self.bool_value,
            self.int_value,
            self.double_value,
            self.bytes_value,
            self.array_value,
            self.kvlist_value,
        )
        if sum(value is not None for value in values) != 1:
            raise ValueError("OTLP AnyValue must contain exactly one value")
        if isinstance(self.int_value, str) and not re.fullmatch(
            r"-?[0-9]+", self.int_value
        ):
            raise ValueError("OTLP intValue strings must be decimal integers")
        return self


class _Attribute(_StrictModel):
    key: StrictStr
    value: _AnyValue


class _ArrayValue(_StrictModel):
    values: list[_AnyValue] = Field(default_factory=list)


class _KeyValueList(_StrictModel):
    values: list[_Attribute] = Field(default_factory=list)


_AnyValue.model_rebuild()


class _Status(_StrictModel):
    message: Optional[StrictStr] = None
    code: Optional[StrictInt] = None


class _Event(_StrictModel):
    time_unix_nano: StrictInt | StrictStr = Field(alias="timeUnixNano")
    name: StrictStr
    attributes: list[_Attribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[StrictInt] = Field(
        default=None, alias="droppedAttributesCount"
    )


class _Link(_StrictModel):
    trace_id: StrictStr = Field(alias="traceId")
    span_id: StrictStr = Field(alias="spanId")
    trace_state: Optional[StrictStr] = Field(default=None, alias="traceState")
    attributes: list[_Attribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[StrictInt] = Field(
        default=None, alias="droppedAttributesCount"
    )
    flags: Optional[StrictInt] = None


class _Span(_StrictModel):
    trace_id: StrictStr = Field(alias="traceId")
    span_id: StrictStr = Field(alias="spanId")
    trace_state: Optional[StrictStr] = Field(default=None, alias="traceState")
    parent_span_id: Optional[StrictStr] = Field(default=None, alias="parentSpanId")
    flags: Optional[StrictInt] = None
    name: StrictStr
    kind: Optional[StrictInt] = None
    start_time_unix_nano: StrictInt | StrictStr = Field(alias="startTimeUnixNano")
    end_time_unix_nano: StrictInt | StrictStr = Field(alias="endTimeUnixNano")
    attributes: list[_Attribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[StrictInt] = Field(
        default=None, alias="droppedAttributesCount"
    )
    events: list[_Event] = Field(default_factory=list)
    dropped_events_count: Optional[StrictInt] = Field(
        default=None, alias="droppedEventsCount"
    )
    links: list[_Link] = Field(default_factory=list)
    dropped_links_count: Optional[StrictInt] = Field(
        default=None, alias="droppedLinksCount"
    )
    status: Optional[_Status] = None


class _Resource(_StrictModel):
    attributes: list[_Attribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[StrictInt] = Field(
        default=None, alias="droppedAttributesCount"
    )


class _InstrumentationScope(_StrictModel):
    name: Optional[StrictStr] = None
    version: Optional[StrictStr] = None
    attributes: list[_Attribute] = Field(default_factory=list)
    dropped_attributes_count: Optional[StrictInt] = Field(
        default=None, alias="droppedAttributesCount"
    )


class _ScopeSpans(_StrictModel):
    scope: Optional[_InstrumentationScope] = None
    spans: list[_Span]
    schema_url: Optional[StrictStr] = Field(default=None, alias="schemaUrl")


class _ResourceSpans(_StrictModel):
    resource: Optional[_Resource] = None
    scope_spans: list[_ScopeSpans] = Field(alias="scopeSpans")
    schema_url: Optional[StrictStr] = Field(default=None, alias="schemaUrl")


class _OtlpEnvelope(_StrictModel):
    resource_spans: list[_ResourceSpans] = Field(alias="resourceSpans")


class _PostCallAudioData(_StrictModel):
    agent_id: StrictStr
    conversation_id: StrictStr
    full_audio: StrictStr = Field(repr=False)


class _PostCallAudioEvent(_StrictModel):
    type: Literal["post_call_audio"]
    data: _PostCallAudioData
    event_timestamp: Optional[StrictInt] = None


@dataclass(frozen=True)
class _SpanRef:
    span: _Span
    resource_attributes: tuple[_Attribute, ...]


def _validation_error(message: str, error: ValidationError) -> ValueError:
    return ValueError(f"{message} ({error.error_count()} validation errors)")


def _parse_otlp(otlp_traces: Mapping[str, JsonValue]) -> _OtlpEnvelope:
    try:
        return _OtlpEnvelope.model_validate(otlp_traces)
    except ValidationError as error:
        raise _validation_error("Invalid OTLP trace envelope", error) from None


def _parse_audio(
    post_call_audio: Optional[Mapping[str, JsonValue]],
) -> Optional[_PostCallAudioData]:
    if post_call_audio is None:
        return None
    try:
        if "data" in post_call_audio:
            return _PostCallAudioEvent.model_validate(post_call_audio).data
        return _PostCallAudioData.model_validate(post_call_audio)
    except ValidationError as error:
        raise _validation_error(
            "Invalid ElevenLabs post_call_audio payload", error
        ) from None


def _collect_spans(envelope: _OtlpEnvelope, max_spans: int) -> list[_SpanRef]:
    if max_spans < 1:
        raise ValueError("max_spans must be a positive integer")

    refs: list[_SpanRef] = []
    for resource_spans in envelope.resource_spans:
        resource_attributes = tuple(
            resource_spans.resource.attributes if resource_spans.resource else ()
        )
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                if len(refs) >= max_spans:
                    raise ValueError(f"OTLP trace exceeds the {max_spans} span limit")
                refs.append(_SpanRef(span, resource_attributes))

    if not refs:
        raise ValueError("OTLP trace must contain at least one span")
    return refs


def _validate_trace(refs: Sequence[_SpanRef]) -> _Span:
    trace_ids: set[str] = set()
    roots: list[_Span] = []
    for ref in refs:
        span = ref.span
        if not _TRACE_ID_RE.fullmatch(span.trace_id):
            raise ValueError("Every OTLP span must have a 32-character hex traceId")
        if not _SPAN_ID_RE.fullmatch(span.span_id):
            raise ValueError("Every OTLP span must have a 16-character hex spanId")
        if span.parent_span_id and not _SPAN_ID_RE.fullmatch(span.parent_span_id):
            raise ValueError("OTLP parentSpanId must be a 16-character hex value")
        trace_ids.add(span.trace_id.lower())
        if span.name == _CONVERSATION_SPAN:
            roots.append(span)

    if len(trace_ids) != 1:
        raise ValueError("An ElevenLabs conversation must contain exactly one traceId")
    if len(roots) != 1:
        raise ValueError(
            "An ElevenLabs conversation must contain exactly one "
            "elevenlabs.conversation root span"
        )
    if roots[0].parent_span_id:
        raise ValueError("The elevenlabs.conversation root span cannot have a parent")
    return roots[0]


def _string_values(attributes: Sequence[_Attribute], key: str) -> list[str]:
    values: list[str] = []
    for attribute in attributes:
        if attribute.key != key:
            continue
        if attribute.value.string_value is None:
            raise ValueError(f"{key} must be an OTLP string attribute")
        values.append(attribute.value.string_value)
    return values


def _identifier_values(refs: Sequence[_SpanRef], key: str) -> list[str]:
    values: list[str] = []
    seen_resources: set[int] = set()
    for ref in refs:
        resource_id = id(ref.resource_attributes)
        if resource_id not in seen_resources:
            seen_resources.add(resource_id)
            values.extend(_string_values(ref.resource_attributes, key))
        values.extend(_string_values(ref.span.attributes, key))
    return values


def _resolve_identifier(
    name: str, candidates: Sequence[Optional[str]], *, required: bool
) -> Optional[str]:
    values = {candidate for candidate in candidates if candidate}
    if len(values) > 1:
        raise ValueError(f"Mismatched {name} values in ElevenLabs payloads")
    if not values:
        if required:
            raise ValueError(f"ElevenLabs OTLP trace is missing {name}")
        return None
    return next(iter(values))


def _first_string(span: _Span, key: str) -> Optional[str]:
    values = _string_values(span.attributes, key)
    return values[0] if values else None


def _set_attribute(span: _Span, key: str, value: str) -> None:
    new_attribute = _Attribute(
        key=key,
        value=_AnyValue(string_value=value),
    )
    attributes = list(span.attributes)
    for index, attribute in enumerate(attributes):
        if attribute.key == key:
            attributes[index] = new_attribute
            span.attributes = attributes
            return
    span.attributes = [*attributes, new_attribute]


def _message(role: Literal["user", "assistant"], content: str) -> str:
    return _orjson.dumps({"messages": [{"role": role, "content": content}]}).decode(
        "utf-8"
    )


def _enrich_span(span: _Span) -> None:
    """Translate only ElevenLabs fields without LangSmith equivalents."""
    if span.name == _CONVERSATION_SPAN:
        _set_attribute(span, "langsmith.span.kind", "chain")
    elif span.name == _USER_TRANSCRIPT_SPAN:
        _set_attribute(span, "langsmith.span.kind", "llm")
        if text := _first_string(span, _USER_TEXT_ATTR):
            _set_attribute(span, "gen_ai.prompt", _message("user", text))
    elif span.name == _AGENT_RESPONSE_SPAN:
        _set_attribute(span, "langsmith.span.kind", "llm")
        if text := _first_string(span, _AGENT_TEXT_ATTR):
            _set_attribute(span, "gen_ai.completion", _message("assistant", text))
    elif span.name.startswith(_TOOL_SPAN_PREFIX):
        _set_attribute(span, "langsmith.span.kind", "tool")


def _validate_audio_base64(value: str, size_limit_bytes: Optional[int]) -> None:
    if not value or len(value) % 4 != 0 or not _BASE64_RE.fullmatch(value):
        raise ValueError("post_call_audio.full_audio is not valid padded base64")
    padding = len(value) - len(value.rstrip("="))
    decoded_size = (len(value) // 4) * 3 - padding
    if size_limit_bytes is not None:
        if size_limit_bytes < 0:
            raise ValueError("audio_size_limit_bytes must be non-negative or None")
        if decoded_size > size_limit_bytes:
            raise ValueError(
                "ElevenLabs post-call audio exceeds the configured decoded-byte limit"
            )


def transform_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    post_call_audio: Optional[Mapping[str, JsonValue]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
) -> dict[str, JsonValue]:
    """Add LangSmith voice fields to one ElevenLabs post-call OTLP trace.

    ElevenLabs' topology, timing, status, IDs, and existing attributes are
    preserved. The combined MP3 is attached to the existing conversation root.
    """
    envelope = _parse_otlp(otlp_traces)
    refs = _collect_spans(envelope, max_spans)
    root = _validate_trace(refs)
    audio = _parse_audio(post_call_audio)

    _resolve_identifier(
        "conversation_id",
        [
            *_identifier_values(refs, _CONVERSATION_ID_ATTR),
            conversation_id,
            audio.conversation_id if audio else None,
        ],
        required=True,
    )
    _resolve_identifier(
        "agent_id",
        [
            *_identifier_values(refs, _AGENT_ID_ATTR),
            agent_id,
            audio.agent_id if audio else None,
        ],
        required=False,
    )

    for ref in refs:
        _enrich_span(ref.span)

    _set_attribute(root, "langsmith.metadata.ls_modality", "audio")
    _set_attribute(root, "langsmith.metadata.ls_integration", "elevenlabs")

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
        _set_attribute(root, "langsmith.attachments", attachment)

    return cast(
        dict[str, JsonValue],
        envelope.model_dump(by_alias=True, exclude_unset=True),
    )


def _project_name(project_name: Optional[str]) -> str:
    if project_name == "":
        raise ValueError("project_name must be a non-empty string")
    return project_name or ls_utils.get_tracer_project() or "default"


@warn_beta
def export_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    post_call_audio: Optional[Mapping[str, JsonValue]] = None,
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
        post_call_audio=post_call_audio,
        conversation_id=conversation_id,
        agent_id=agent_id,
        audio_size_limit_bytes=audio_size_limit_bytes,
        max_spans=max_spans,
    )
    owns_client = client is None
    resolved_client = client or Client()
    try:
        response: requests.Response = resolved_client.request_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            data=_orjson.dumps(payload),
            headers={"Langsmith-Project": _project_name(project_name)},
        )
        del response
    finally:
        if owns_client:
            resolved_client.close()
    return payload


@warn_beta
async def aexport_elevenlabs_trace(
    otlp_traces: Mapping[str, JsonValue],
    *,
    post_call_audio: Optional[Mapping[str, JsonValue]] = None,
    conversation_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    audio_size_limit_bytes: Optional[int] = DEFAULT_AUDIO_SIZE_LIMIT,
    max_spans: int = DEFAULT_MAX_SPANS,
    client: Optional[AsyncClient] = None,
    project_name: Optional[str] = None,
) -> dict[str, JsonValue]:
    """Transform and asynchronously export one ElevenLabs conversation trace."""
    from langsmith.async_client import AsyncClient

    payload = transform_elevenlabs_trace(
        otlp_traces,
        post_call_audio=post_call_audio,
        conversation_id=conversation_id,
        agent_id=agent_id,
        audio_size_limit_bytes=audio_size_limit_bytes,
        max_spans=max_spans,
    )
    owns_client = client is None
    resolved_client = client or AsyncClient()
    try:
        response: httpx.Response = await resolved_client._arequest_with_retries(
            "POST",
            "otel/v1/traces",
            stop_after_attempt=3,
            content=_orjson.dumps(payload),
            headers={"Langsmith-Project": _project_name(project_name)},
        )
        del response
    finally:
        if owns_client:
            await resolved_client.aclose()
    return payload
