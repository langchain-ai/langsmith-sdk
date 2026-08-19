"""Unit tests for the ElevenLabs post-call tracing integration."""

from __future__ import annotations

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
                        "scope": {"name": "elevenlabs.convai", "version": "1"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def _spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def _attrs(span: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in span["attributes"]:
        value = attribute["value"]
        result[attribute["key"]] = next(iter(value.values()))
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
        post_call_audio=_audio_event(),
        metadata={"environment": "test"},
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
    assert root_attrs["langsmith.metadata.thread_id"] == "conv-123"
    assert root_attrs["langsmith.metadata.environment"] == "test"
    assert json.loads(root_attrs["gen_ai.prompt"]) == {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
    }
    assert json.loads(root_attrs["langsmith.attachments"]) == [
        {
            "name": "conversation.mp3",
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

    agent_attrs = _attrs(spans[2])
    assert agent_attrs["langsmith.span.kind"] == "llm"
    assert json.loads(agent_attrs["gen_ai.prompt"])["messages"] == [
        {"role": "user", "content": "Hello"}
    ]
    assert json.loads(agent_attrs["gen_ai.completion"])["messages"] == [
        {"role": "assistant", "content": "Hi there"}
    ]

    tool_attrs = _attrs(spans[3])
    assert tool_attrs["langsmith.span.kind"] == "tool"
    assert tool_attrs["gen_ai.prompt"] == '{"city":"SF"}'
    assert tool_attrs["gen_ai.completion"] == '{"temp":70}'
    assert tool_attrs["elevenlabs.tool.arguments"] == '{"city":"SF"}'

    assert all(
        _attrs(span)["langsmith.metadata.thread_id"] == "conv-123" for span in spans
    )


def test_transform_without_audio_still_marks_voice_modality() -> None:
    transformed = transform_elevenlabs_trace(_fixture())
    root_attrs = _attrs(_spans(transformed)[0])

    assert root_attrs["langsmith.metadata.ls_modality"] == "audio"
    assert "langsmith.attachments" not in root_attrs


@pytest.mark.parametrize(
    "audio",
    [
        {
            "conversation_id": "other-conversation",
            "agent_id": "agent-456",
            "full_audio": "bXAz",
        },
        {
            "conversation_id": "conv-123",
            "agent_id": "other-agent",
            "full_audio": "bXAz",
        },
    ],
)
def test_transform_rejects_mismatched_audio_identity(audio: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Mismatched"):
        transform_elevenlabs_trace(_fixture(), post_call_audio=audio)


@pytest.mark.parametrize("audio", ["not base64", "abc", "===="])
def test_transform_rejects_invalid_audio_base64(audio: str) -> None:
    with pytest.raises(ValueError, match="valid padded base64"):
        transform_elevenlabs_trace(_fixture(), post_call_audio=_audio_event(audio))


def test_transform_rejects_oversized_audio() -> None:
    with pytest.raises(ValueError, match="decoded-byte limit"):
        transform_elevenlabs_trace(
            _fixture(), post_call_audio=_audio_event(), audio_size_limit_bytes=2
        )


def test_transform_requires_one_trace_and_one_root() -> None:
    mixed_trace = _fixture()
    _spans(mixed_trace)[1]["traceId"] = "b" * 32
    with pytest.raises(ValueError, match="exactly one traceId"):
        transform_elevenlabs_trace(mixed_trace)

    duplicate_root = _fixture()
    duplicate_root_span = copy.deepcopy(_spans(duplicate_root)[0])
    duplicate_root_span["spanId"] = "5" * 16
    _spans(duplicate_root).append(duplicate_root_span)
    with pytest.raises(ValueError, match="exactly one elevenlabs.conversation"):
        transform_elevenlabs_trace(duplicate_root)


def test_transform_enforces_span_limit() -> None:
    with pytest.raises(ValueError, match="3 span limit"):
        transform_elevenlabs_trace(_fixture(), max_spans=3)


def test_anonymizer_runs_before_audio_and_must_preserve_identity() -> None:
    saw_attachment = False

    def anonymize(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal saw_attachment
        for span in _spans(payload):
            attrs = _attrs(span)
            saw_attachment = saw_attachment or "langsmith.attachments" in attrs
            for attribute in span["attributes"]:
                if attribute["key"] == "elevenlabs.user.text":
                    attribute["value"] = {"stringValue": "[redacted]"}
        return payload

    transformed = transform_elevenlabs_trace(
        _fixture(), post_call_audio=_audio_event(), anonymizer=anonymize
    )

    assert saw_attachment is False
    assert _attrs(_spans(transformed)[1])["elevenlabs.user.text"] == "[redacted]"
    assert "langsmith.attachments" in _attrs(_spans(transformed)[0])

    def alter_identity(payload: dict[str, Any]) -> dict[str, Any]:
        _spans(payload)[0]["spanId"] = "f" * 16
        return payload

    with pytest.raises(ValueError, match="cannot modify OTLP trace topology"):
        transform_elevenlabs_trace(_fixture(), anonymizer=alter_identity)


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
