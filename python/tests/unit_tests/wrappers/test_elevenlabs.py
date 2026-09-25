"""Unit tests for the ElevenLabs post-call tracing integration."""

from __future__ import annotations

import base64
import copy
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from langsmith.integrations.elevenlabs import (
    aexport_elevenlabs_trace,
    export_elevenlabs_trace,
    transform_elevenlabs_trace,
)
from langsmith.utils import LangSmithConflictError

TRACE_ID = "a" * 32
ROOT_SPAN_ID = "1" * 16


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        encoded = {"stringValue": value}
    elif isinstance(value, bool):
        encoded = {"boolValue": value}
    else:
        raise TypeError(value)
    return {"key": key, "value": encoded}


def _span(
    name: str,
    span_id: str,
    start: int,
    *,
    parent_span_id: str | None = ROOT_SPAN_ID,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    span = {
        "traceId": TRACE_ID,
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(start + 1),
        "attributes": attributes or [],
        "status": {"code": 1},
    }
    if parent_span_id is not None:
        span["parentSpanId"] = parent_span_id
    return span


def _fixture() -> dict[str, Any]:
    """An OTLP envelope shaped like ElevenLabs' documented post-call trace."""
    spans = [
        _span(
            "elevenlabs.conversation",
            ROOT_SPAN_ID,
            1,
            parent_span_id=None,
            attributes=[_attr("elevenlabs.source", "post_call_webhook")],
        ),
        _span(
            "elevenlabs.recv.user_transcript",
            "2" * 16,
            2,
            attributes=[_attr("elevenlabs.user.text", "Hello")],
        ),
        _span(
            "elevenlabs.recv.agent_response",
            "3" * 16,
            3,
            attributes=[_attr("elevenlabs.agent.text", "Hi there")],
        ),
        _span(
            "elevenlabs.tool.weather",
            "4" * 16,
            4,
            parent_span_id="3" * 16,
            attributes=[
                _attr("elevenlabs.tool.arguments", '{"city":"SF"}'),
                _attr("elevenlabs.tool.result", '{"temp":70}'),
            ],
        ),
    ]
    spans[0]["traceState"] = "vendor=value"
    spans[0]["kind"] = 1
    spans[0]["events"] = [
        {
            "timeUnixNano": "2",
            "name": "conversation.started",
            "attributes": [_attr("event.detail", "preserved")],
        }
    ]
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _attr("service.name", "elevenlabs-convai"),
                        _attr("elevenlabs.conversation_id", "conv-123"),
                        _attr("elevenlabs.agent_id", "agent-456"),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "elevenlabs.convai", "version": "1.0.0"},
                        "spans": spans,
                    }
                ],
                "schemaUrl": "https://opentelemetry.io/schemas/1.30.0",
            }
        ]
    }


def _otel_event() -> dict[str, Any]:
    """The full ``post_call_transcription_otel`` webhook body."""
    return {
        "type": "post_call_transcription_otel",
        "event_timestamp": 1_700_000_000,
        "data": {
            "conversation_id": "conv-123",
            "agent_id": "agent-456",
            "otlp_traces": _fixture(),
        },
    }


def _spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def _attrs(span: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in span["attributes"]:
        value = attribute["value"]
        result[attribute["key"]] = next(iter(value.values()), None)
    return result


def _audio_event(audio: str = "bXAz") -> dict[str, Any]:
    return {
        "type": "post_call_audio",
        "event_timestamp": 1_700_000_000,
        "data": {
            "conversation_id": "conv-123",
            "agent_id": "agent-456",
            "full_audio": audio,
        },
    }


def test_transform_builds_one_audio_aware_trace() -> None:
    original = _fixture()
    untouched = copy.deepcopy(original)

    transformed = transform_elevenlabs_trace(
        original,
        audio=_audio_event(),
    )

    assert original == untouched
    spans = _spans(transformed)
    assert {span["traceId"] for span in spans} == {TRACE_ID}
    assert [span["parentSpanId"] for span in spans[1:3]] == [
        ROOT_SPAN_ID,
        ROOT_SPAN_ID,
    ]

    root_attrs = _attrs(spans[0])
    assert root_attrs["langsmith.span.kind"] == "chain"
    assert root_attrs["langsmith.root_span"] is True
    assert root_attrs["langsmith.metadata.ls_modality"] == "audio"
    assert root_attrs["langsmith.metadata.ls_integration"] == "elevenlabs"
    # ElevenLabs' own tracer version, from the payload's instrumentation scope.
    assert root_attrs["langsmith.metadata.ls_integration_version"] == "1.0.0"
    assert root_attrs["langsmith.metadata.elevenlabs_trace_id"] == TRACE_ID
    assert root_attrs["langsmith.metadata.conversation_id"] == "conv-123"
    assert root_attrs["langsmith.metadata.agent_id"] == "agent-456"
    assert root_attrs["langsmith.metadata.elevenlabs_source"] == "post_call_webhook"
    assert "gen_ai.prompt" not in root_attrs
    assert json.loads(root_attrs["langsmith.attachments"]) == [
        {
            "name": "conversation_mp3",
            "content": "bXAz",
            "mime_type": "audio/mpeg",
        }
    ]

    user_attrs = _attrs(spans[1])
    assert user_attrs["langsmith.span.kind"] == "llm"
    assert json.loads(user_attrs["gen_ai.prompt"])["messages"][0] == {
        "role": "user",
        "content": "Hello",
    }
    assert user_attrs["langsmith.metadata.elevenlabs_user_text"] == "Hello"

    agent_attrs = _attrs(spans[2])
    assert agent_attrs["langsmith.span.kind"] == "llm"
    assert "gen_ai.prompt" not in agent_attrs
    assert json.loads(agent_attrs["gen_ai.completion"])["messages"] == [
        {"role": "assistant", "content": "Hi there"}
    ]

    tool_attrs = _attrs(spans[3])
    assert tool_attrs["langsmith.span.kind"] == "tool"
    assert tool_attrs["langsmith.metadata.tool_name"] == "weather"
    assert tool_attrs["gen_ai.prompt"] == '{"city":"SF"}'
    assert tool_attrs["gen_ai.completion"] == '{"temp":70}'
    assert tool_attrs["elevenlabs.tool.arguments"] == '{"city":"SF"}'

    # Every span joins the conversation's thread.
    for span in spans:
        assert _attrs(span)["langsmith.metadata.thread_id"] == "conv-123"

    assert spans[0]["traceState"] == "vendor=value"
    assert spans[0]["kind"] == 1
    assert (
        spans[0]["events"]
        == original["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["events"]
    )
    assert transformed["resourceSpans"][0]["schemaUrl"] == (
        "https://opentelemetry.io/schemas/1.30.0"
    )


def test_transform_takes_the_otlp_envelope_from_a_webhook_event() -> None:
    """The caller unwraps; the ids come from the trace's own resource attributes."""
    transformed = transform_elevenlabs_trace(_otel_event()["data"]["otlp_traces"])
    root_attrs = _attrs(_spans(transformed)[0])

    assert transformed.keys() == {"resourceSpans"}
    assert root_attrs["langsmith.metadata.conversation_id"] == "conv-123"
    assert root_attrs["langsmith.metadata.thread_id"] == "conv-123"


def test_transform_accepts_raw_audio_bytes() -> None:
    transformed = transform_elevenlabs_trace(_fixture(), audio=b"ID3" + b"\x00" * 40)
    attachments = json.loads(_attrs(_spans(transformed)[0])["langsmith.attachments"])

    assert attachments[0]["name"] == "conversation_mp3"  # periods are rejected
    assert attachments[0]["mime_type"] == "audio/mpeg"
    assert base64.b64decode(attachments[0]["content"]) == b"ID3" + b"\x00" * 40


def test_transform_skips_oversized_raw_audio() -> None:
    transformed = transform_elevenlabs_trace(
        _fixture(), audio=b"x" * 100, audio_size_limit_bytes=10
    )

    assert "langsmith.attachments" not in _attrs(_spans(transformed)[0])


def test_transform_maps_llm_usage_to_usage_metadata() -> None:
    payload = _fixture()
    _spans(payload)[2]["attributes"].extend(
        [
            _attr(
                "elevenlabs.llm_usage.gemini-2.5-flash.input",
                "{'tokens': 120, 'price': 0.00018}",
            ),
            _attr(
                "elevenlabs.llm_usage.gemini-2.5-flash.output_total",
                "{'tokens': 30, 'price': 1.7e-05}",
            ),
            _attr(
                "elevenlabs.llm_usage.gemini-2.5-flash.input_cache_read",
                "{'tokens': 80, 'price': 0.0}",
            ),
        ]
    )

    agent_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[2])

    # Cache reads sit alongside `input`, not inside it, so the prompt total is
    # their sum and the detail stays a subset of it.
    assert json.loads(agent_attrs["langsmith.usage_metadata"]) == {
        "input_tokens": 200,
        "output_tokens": 30,
        "total_tokens": 230,
        "input_token_details": {"cache_read": 80},
    }
    # The model name contains dots, so only the last component is the field.
    assert agent_attrs["gen_ai.request.model"] == "gemini-2.5-flash"
    assert agent_attrs["langsmith.metadata.ls_model_name"] == "gemini-2.5-flash"
    assert agent_attrs["langsmith.metadata.ls_provider"] == "google"


def test_transform_names_the_model_from_the_span_attribute() -> None:
    """ElevenLabs names the model directly; usage keys are only the fallback."""
    payload = _fixture()
    _spans(payload)[2]["attributes"].append(
        _attr("elevenlabs.producing_llm", "claude-sonnet-4")
    )

    agent_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[2])

    assert agent_attrs["langsmith.metadata.ls_model_name"] == "claude-sonnet-4"
    assert agent_attrs["langsmith.metadata.ls_provider"] == "anthropic"
    # LangSmith reads either gen_ai provider key, so both are written.
    assert agent_attrs["gen_ai.system"] == "anthropic"
    assert agent_attrs["gen_ai.provider.name"] == "anthropic"


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("gemini-2.5-flash", "google"),
        ("gpt-4o-mini", "openai"),
        ("o3-mini", "openai"),
        ("claude-sonnet-4", "anthropic"),
        ("grok-3", "xai"),
        ("mistral-large", "mistralai"),
    ],
)
def test_transform_maps_models_to_langsmith_providers(
    model: str, provider: str
) -> None:
    payload = _fixture()
    _spans(payload)[2]["attributes"].append(_attr("elevenlabs.producing_llm", model))

    agent_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[2])

    assert agent_attrs["langsmith.metadata.ls_provider"] == provider


def test_transform_leaves_provider_unset_for_an_unknown_model() -> None:
    """A custom LLM should not be guessed at — a wrong ls_provider misprices."""
    payload = _fixture()
    _spans(payload)[2]["attributes"].append(
        _attr("elevenlabs.producing_llm", "acme-internal-v3")
    )

    agent_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[2])

    assert agent_attrs["langsmith.metadata.ls_model_name"] == "acme-internal-v3"
    assert "langsmith.metadata.ls_provider" not in agent_attrs


def test_transform_leaves_usage_alone_when_two_models_share_a_span() -> None:
    payload = _fixture()
    _spans(payload)[2]["attributes"].extend(
        [
            _attr("elevenlabs.llm_usage.gemini-2.5-flash.input", "{'tokens': 10}"),
            _attr("elevenlabs.llm_usage.gpt-4o.input", "{'tokens': 5}"),
        ]
    )

    agent_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[2])

    assert json.loads(agent_attrs["langsmith.usage_metadata"])["input_tokens"] == 15
    assert "gen_ai.request.model" not in agent_attrs


def test_transform_translates_monitoring_turn_and_event_spans() -> None:
    payload = _fixture()
    _spans(payload)[1:] = [
        _span("elevenlabs.turn.0", "5" * 16, 5),
        _span(
            "elevenlabs.event.user_transcript",
            "6" * 16,
            6,
            parent_span_id="5" * 16,
            attributes=[_attr("elevenlabs.user.text", "Hi")],
        ),
    ]

    spans = _spans(transform_elevenlabs_trace(payload))

    turn_attrs = _attrs(spans[1])
    assert turn_attrs["langsmith.span.kind"] == "chain"
    assert turn_attrs["langsmith.metadata.turn_number"] == "0"

    event_attrs = _attrs(spans[2])
    assert event_attrs["langsmith.span.kind"] == "llm"
    assert json.loads(event_attrs["gen_ai.prompt"])["messages"][0]["content"] == "Hi"


def test_transform_passes_unknown_payloads_through_untouched() -> None:
    """Unrecognized OTLP fields and attributes must survive, not fail the export."""
    payload = _fixture()
    span = _spans(payload)[0]
    span["kind"] = "SPAN_KIND_SERVER"  # protojson serializes enums as names
    span["status"] = {"code": "STATUS_CODE_OK"}
    span["somethingNew"] = "kept"
    span["attributes"].append({"key": "elevenlabs.future.metric", "value": {}})
    span["attributes"].append(_attr("elevenlabs.cost.credits", "42"))
    payload["resourceSpans"][0]["entityRefs"] = []

    transformed = transform_elevenlabs_trace(payload)

    root = _spans(transformed)[0]
    assert root["kind"] == "SPAN_KIND_SERVER"
    assert root["status"] == {"code": "STATUS_CODE_OK"}
    assert root["somethingNew"] == "kept"
    assert transformed["resourceSpans"][0]["entityRefs"] == []
    # An unrecognized vendor attribute still reaches LangSmith as metadata.
    assert _attrs(root)["langsmith.metadata.elevenlabs_cost_credits"] == "42"


def test_transform_tolerates_a_payload_with_no_scope_version() -> None:
    payload = _fixture()
    del payload["resourceSpans"][0]["scopeSpans"][0]["scope"]

    root_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[0])

    assert root_attrs["langsmith.metadata.ls_integration"] == "elevenlabs"
    assert root_attrs["langsmith.metadata.ls_integration_version"] == ""


def test_transform_without_audio_still_marks_voice_modality() -> None:
    transformed = transform_elevenlabs_trace(_fixture())
    root_attrs = _attrs(_spans(transformed)[0])

    assert root_attrs["langsmith.metadata.ls_modality"] == "audio"
    assert "langsmith.attachments" not in root_attrs


def test_transform_rejects_audio_from_another_conversation() -> None:
    """The one guard that matters: never staple call A's recording to call B."""
    audio = {
        "conversation_id": "other-conversation",
        "agent_id": "agent-456",
        "full_audio": "bXAz",
    }
    with pytest.raises(ValueError, match="Mismatched"):
        transform_elevenlabs_trace(_fixture(), audio=audio)


def test_transform_cannot_check_identity_of_raw_bytes() -> None:
    """Raw bytes carry no conversation id, so the caller owns the pairing."""
    transformed = transform_elevenlabs_trace(_fixture(), audio=b"ID3anything")

    assert "langsmith.attachments" in _attrs(_spans(transformed)[0])


@pytest.mark.parametrize("audio", ["not base64", "abc", "===="])
def test_transform_skips_invalid_audio_but_keeps_the_trace(audio: str) -> None:
    transformed = transform_elevenlabs_trace(_fixture(), audio=_audio_event(audio))
    root_attrs = _attrs(_spans(transformed)[0])

    assert "langsmith.attachments" not in root_attrs
    assert root_attrs["langsmith.metadata.ls_modality"] == "audio"


def test_transform_skips_oversized_audio_but_keeps_the_trace() -> None:
    transformed = transform_elevenlabs_trace(
        _fixture(), audio=_audio_event(), audio_size_limit_bytes=2
    )

    assert "langsmith.attachments" not in _attrs(_spans(transformed)[0])


def test_transform_requires_spans_and_honors_the_span_limit() -> None:
    with pytest.raises(ValueError, match="contains no spans"):
        transform_elevenlabs_trace({"resourceSpans": []})

    with pytest.raises(ValueError, match="3 span limit"):
        transform_elevenlabs_trace(_fixture(), max_spans=3)


def test_transform_falls_back_to_the_parentless_root() -> None:
    payload = _fixture()
    _spans(payload)[0]["name"] = "elevenlabs.session"

    root_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[0])

    assert root_attrs["langsmith.root_span"] is True
    assert root_attrs["langsmith.metadata.ls_integration"] == "elevenlabs"


def test_transform_without_conversation_id_still_exports() -> None:
    payload = _fixture()
    payload["resourceSpans"][0]["resource"]["attributes"] = []

    root_attrs = _attrs(_spans(transform_elevenlabs_trace(payload))[0])

    assert "langsmith.metadata.thread_id" not in root_attrs
    assert root_attrs["langsmith.metadata.ls_modality"] == "audio"


def test_sync_export_uses_langsmith_otel_endpoint() -> None:
    client = MagicMock()
    client.request_with_retries.return_value = MagicMock()

    transformed = export_elevenlabs_trace(
        _fixture(), client=client, project_name="voice-project"
    )

    client.request_with_retries.assert_called_once()
    args, kwargs = client.request_with_retries.call_args
    assert args == ("POST", "otel/v1/traces")
    assert kwargs["stop_after_attempt"] == 3
    assert kwargs["headers"] == {"Langsmith-Project": "voice-project"}
    assert json.loads(kwargs["data"]) == transformed
    assert not client.close.called


def test_sync_export_treats_a_redelivery_as_success() -> None:
    """ElevenLabs retries the transcript webhook; LangSmith 409s the repeat."""
    client = MagicMock()
    client.request_with_retries.side_effect = LangSmithConflictError("duplicate")

    payload = export_elevenlabs_trace(_fixture(), client=client)

    assert payload["resourceSpans"]


@pytest.mark.asyncio
async def test_async_export_treats_a_redelivery_as_success() -> None:
    client = MagicMock()
    client._arequest_with_retries = AsyncMock(
        side_effect=LangSmithConflictError("duplicate")
    )

    payload = await aexport_elevenlabs_trace(_fixture(), client=client)

    assert payload["resourceSpans"]


@pytest.mark.asyncio
async def test_async_export_uses_langsmith_otel_endpoint() -> None:
    client = MagicMock()
    client._arequest_with_retries = AsyncMock(return_value=MagicMock())

    transformed = await aexport_elevenlabs_trace(
        _fixture(), client=client, project_name="voice-project"
    )

    client._arequest_with_retries.assert_awaited_once()
    args, kwargs = client._arequest_with_retries.call_args
    assert args == ("POST", "otel/v1/traces")
    assert kwargs["stop_after_attempt"] == 3
    assert kwargs["headers"] == {"Langsmith-Project": "voice-project"}
    assert json.loads(kwargs["content"]) == transformed
