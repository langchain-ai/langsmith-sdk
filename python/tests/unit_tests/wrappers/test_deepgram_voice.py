"""Unit tests for Deepgram Voice Agent WebSocket tracing."""

from __future__ import annotations

import json
import subprocess
import sys
from unittest import mock

import pytest

from langsmith import Client
from langsmith._internal.voice import session as session_mod
from langsmith.integrations.deepgram_voice import _connection as voice_mod
from langsmith.integrations.deepgram_voice import wrap_deepgram_voice

LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


@pytest.fixture
def mock_client() -> Client:
    return Client(session=mock.MagicMock(), info=LS_TEST_CLIENT_INFO, api_key="test")


@pytest.fixture(autouse=True)
def _patch_cached_client(mock_client, monkeypatch):
    monkeypatch.setattr(
        "langsmith.run_trees.get_cached_client", lambda **_: mock_client
    )


class FakeConnection:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.connection_id = "provider-connection"
        self._iterator = None

    def __aiter__(self):
        self._iterator = iter(self.frames)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def recv(self):
        if not self.frames:
            raise RuntimeError("no frames")
        return self.frames.pop(0)

    async def send(self, frame):
        self.sent.append(frame)


class FakeSdkMessage:
    """Dependency-free stand-in for a Deepgram SDK Pydantic message."""

    def __init__(self, **value):
        self.value = value

    def model_dump(self, *, mode, exclude_none):
        assert mode == "json"
        assert exclude_none is True
        return self.value


class FakeSdkConnection:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent_settings = []
        self.sent_function_responses = []
        self.sent_media = []
        self._iterator = None

    def __aiter__(self):
        self._iterator = iter(self.frames)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def recv(self):
        if not self.frames:
            raise RuntimeError("no frames")
        return self.frames.pop(0)

    async def send_settings(self, message):
        self.sent_settings.append(message)

    async def send_function_call_response(self, message):
        self.sent_function_responses.append(message)

    async def send_media(self, frame):
        self.sent_media.append(frame)


def _frame(message_type, **fields):
    return json.dumps({"type": message_type, **fields})


def _spy_children(monkeypatch):
    created = []
    real = session_mod.RunTree.create_child

    def spy(self, **kwargs):
        child = real(self, **kwargs)
        created.append((kwargs.get("name"), child))
        return child

    monkeypatch.setattr(session_mod.RunTree, "create_child", spy)
    return created


def test_import_does_not_load_websocket_packages():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import langsmith.integrations.deepgram_voice; "
                "assert 'websockets' not in sys.modules; "
                "assert 'deepgram' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


async def test_proxy_is_transparent_and_tracing_fails_open(monkeypatch):
    frames = [_frame("Welcome", request_id="request-1"), b"\x00\x01"]
    raw = FakeConnection(frames)
    monkeypatch.setattr(
        voice_mod._DeepgramVoiceTracer,
        "observe",
        mock.Mock(side_effect=RuntimeError("broken tracer")),
    )
    seen = []
    async with wrap_deepgram_voice(raw) as connection:
        assert connection.connection_id == "provider-connection"
        await connection.send(_frame("Settings", agent={}))
        async for frame in connection:
            seen.append(frame)
    assert seen == frames
    assert raw.sent == [_frame("Settings", agent={})]


async def test_proxy_supports_typed_deepgram_sdk_messages(monkeypatch):
    created = _spy_children(monkeypatch)
    settings = FakeSdkMessage(
        type="Settings",
        audio={"input": {"encoding": "linear16", "sample_rate": 24_000}},
        agent={
            "listen": {"provider": {"type": "deepgram", "model": "nova-3"}},
            "think": {"provider": {"type": "open_ai", "model": "gpt-4o-mini"}},
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
        },
    )
    function_response = FakeSdkMessage(
        type="FunctionCallResponse",
        id="call-1",
        name="lookup_weather",
        content='{"temperature": 21}',
    )
    audio = b"\x01\x02" * 120
    raw = FakeSdkConnection(
        [
            FakeSdkMessage(type="Welcome", request_id="request-1"),
            FakeSdkMessage(type="SettingsApplied"),
            FakeSdkMessage(type="UserStartedSpeaking"),
            FakeSdkMessage(
                type="ConversationText", role="user", content="Weather in Paris?"
            ),
            FakeSdkMessage(
                type="FunctionCallRequest",
                functions=[
                    {
                        "id": "call-1",
                        "name": "lookup_weather",
                        "arguments": '{"city":"Paris"}',
                        "client_side": True,
                    }
                ],
            ),
            FakeSdkMessage(type="AgentThinking"),
            FakeSdkMessage(
                type="ConversationText",
                role="assistant",
                content="It is 21 degrees.",
            ),
            audio,
            FakeSdkMessage(type="AgentAudioDone"),
        ]
    )

    async with wrap_deepgram_voice(raw) as connection:
        await connection.send_settings(settings)
        assert isinstance(await connection.recv(), FakeSdkMessage)
        assert isinstance(await connection.recv(), FakeSdkMessage)
        assert isinstance(await connection.recv(), FakeSdkMessage)
        assert isinstance(await connection.recv(), FakeSdkMessage)
        assert isinstance(await connection.recv(), FakeSdkMessage)
        await connection.send_function_call_response(function_response)
        await connection.send_media(b"microphone audio")
        async for _ in connection:
            pass
        trace = connection._session

    assert raw.sent_settings == [settings]
    assert raw.sent_function_responses == [function_response]
    assert raw.sent_media == [b"microphone audio"]
    assert trace.messages == [
        {"role": "user", "content": "Weather in Paris?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "lookup_weather",
                        "arguments": '{"city":"Paris"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "lookup_weather",
            "content": '{"temperature": 21}',
        },
        {"role": "assistant", "content": "It is 21 degrees."},
    ]
    assert len([run for name, run in created if name == "lookup_weather"]) == 1
    assert not any(isinstance(run.inputs, bytes) for _, run in created)


async def test_events_roll_up_into_turn_without_synthetic_model_spans(monkeypatch):
    created = _spy_children(monkeypatch)
    settings = _frame(
        "Settings",
        audio={
            "input": {"encoding": "linear16", "sample_rate": 24_000},
            "output": {"encoding": "linear16", "sample_rate": 24_000},
        },
        agent={
            "listen": {"provider": {"type": "deepgram", "model": "nova-3"}},
            "think": {"provider": {"type": "open_ai", "model": "gpt-4o-mini"}},
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
        },
    )
    audio_chunk = b"\x01\x02" * 240
    frames = [
        _frame("Welcome", request_id="request-1"),
        _frame("SettingsApplied"),
        _frame("UserStartedSpeaking"),
        _frame("ConversationText", role="user", content="Hello"),
        _frame("AgentThinking"),
        _frame("ConversationText", role="assistant", content="Hi there"),
        audio_chunk,
        audio_chunk,
        _frame("AgentAudioDone"),
        _frame(
            "LatencyReport",
            stt_latency=0.12,
            ttt_token_latency=0.34,
            ttt_text_latency=0.36,
            ttt_tool_latency=0.41,
            ttt_thinking_latency=0.29,
            tts_latency=0.18,
            total_latency=0.64,
            unknown_latency="not captured",
        ),
    ]
    async with wrap_deepgram_voice(
        FakeConnection(frames), thread_id="thread-1"
    ) as connection:
        await connection.send(settings)
        async for _ in connection:
            pass
        trace = connection._session
        assert trace._current_turn is None

    assert trace.messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    assert trace.run.name == "Hello"
    assert trace.run.outputs == {"messages": trace.messages}
    root_metadata = (trace.run.extra or {}).get("metadata") or {}
    assert root_metadata["ls_integration"] == "deepgram-voice"
    assert root_metadata["ls_provider"] == "deepgram"
    assert root_metadata["deepgram_request_id"] == "request-1"
    assert root_metadata["deepgram_audio_input_sample_rate"] == 24_000

    conversation_events = [run for name, run in created if name == "ConversationText"]
    assert len(conversation_events) == 2
    assert conversation_events[0].inputs == {
        "role": "user",
        "content": "Hello",
    }
    assert conversation_events[0].outputs == {}
    assert conversation_events[1].inputs == {}
    assert conversation_events[1].outputs == {
        "role": "assistant",
        "content": "Hi there",
    }

    thinking = [run for name, run in created if name == "AgentThinking"]
    assert len(thinking) == 1
    assert thinking[0].outputs == {"type": "AgentThinking"}

    audio_done = [run for name, run in created if name == "AgentAudioDone"]
    assert len(audio_done) == 1
    assert audio_done[0].outputs == {"type": "AgentAudioDone"}

    turns = [run for name, run in created if name == "turn"]
    assert len(turns) == 1
    turn_metadata = (turns[0].extra or {}).get("metadata") or {}
    assert turn_metadata["deepgram_stt_latency_ms"] == 120
    assert turn_metadata["deepgram_ttt_token_latency_ms"] == 340
    assert turn_metadata["deepgram_ttt_text_latency_ms"] == 360
    assert turn_metadata["deepgram_ttt_tool_latency_ms"] == 410
    assert turn_metadata["deepgram_ttt_thinking_latency_ms"] == 290
    assert turn_metadata["deepgram_tts_latency_ms"] == 180
    assert turn_metadata["deepgram_total_latency_ms"] == 640
    assert turns[0].inputs == {"messages": [{"role": "user", "content": "Hello"}]}
    assert turns[0].outputs == {
        "messages": [{"role": "assistant", "content": "Hi there"}]
    }

    names = [name for name, _ in created]
    assert not {"user_message", "model", "agent_audio"}.intersection(names)
    assert not {
        "Welcome",
        "SettingsApplied",
        "UserStartedSpeaking",
        "LatencyReport",
    }.intersection(names)
    assert "unknown_latency" not in turn_metadata


async def test_binary_audio_is_not_traced_and_barge_in_marks_turn(monkeypatch):
    created = _spy_children(monkeypatch)
    first_chunk = b"\x01\x02" * 120
    late_chunk = b"\x03\x04" * 120
    frames = [
        _frame("UserStartedSpeaking"),
        _frame("ConversationText", role="user", content="first question"),
        _frame("ConversationText", role="assistant", content="long answer"),
        first_chunk,
        _frame("UserStartedSpeaking"),
        late_chunk,
        _frame("AgentAudioDone"),
        _frame("ConversationText", role="user", content="second question"),
    ]
    async with wrap_deepgram_voice(
        FakeConnection(frames), is_agent_speaking=lambda: True
    ) as connection:
        async for _ in connection:
            pass

    assert not any(name == "agent_audio" for name, _ in created)
    assert len([run for name, run in created if name == "AgentAudioDone"]) == 1

    turns = [run for name, run in created if name == "turn"]
    assert len(turns) == 2
    assert turns[0].inputs == {
        "messages": [{"role": "user", "content": "first question"}]
    }
    assert turns[0].outputs == {
        "messages": [{"role": "assistant", "content": "long answer"}]
    }
    first_turn_metadata = (turns[0].extra or {}).get("metadata") or {}
    assert first_turn_metadata["was_interrupted"] is True
    assert turns[1].inputs == {
        "messages": [{"role": "user", "content": "second question"}]
    }
    assert turns[1].outputs == {}


async def test_history_is_summarized_on_root_without_a_span(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        _frame(
            "History",
            history=[
                {"role": "user", "content": "private prior input"},
                {"role": "assistant", "content": "private prior output"},
            ],
        )
    ]
    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass
        trace = connection._session

    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["deepgram_history_message_count"] == 2
    assert not any(name == "History" for name, _ in created)
    assert "private prior input" not in repr(metadata)


async def test_tool_response_closes_tool_span(monkeypatch):
    created = _spy_children(monkeypatch)
    request = _frame(
        "FunctionCallRequest",
        functions=[
            {
                "id": "call-1",
                "name": "lookup_weather",
                "arguments": '{"city":"Paris"}',
                "client_side": True,
            }
        ],
    )
    started = _frame("UserStartedSpeaking")
    user_text = _frame("ConversationText", role="user", content="Weather in Paris?")
    tool_latency = _frame("LatencyReport", ttt_tool_latency=0.1)
    thinking = _frame("AgentThinking")
    assistant_text = _frame(
        "ConversationText", role="assistant", content="It is 21 degrees."
    )
    audio_done = _frame("AgentAudioDone")
    raw = FakeConnection(
        [
            started,
            user_text,
            request,
            tool_latency,
            thinking,
            assistant_text,
            audio_done,
        ]
    )
    async with wrap_deepgram_voice(raw) as connection:
        assert await connection.recv() == started
        assert await connection.recv() == user_text
        assert await connection.recv() == request
        assert await connection.recv() == tool_latency
        assert connection._session.has_open_turn is True
        await connection.send(
            _frame(
                "FunctionCallResponse",
                id="call-1",
                name="lookup_weather",
                content='{"temperature": 21}',
            )
        )
        assert await connection.recv() == thinking
        assert await connection.recv() == assistant_text
        assert await connection.recv() == audio_done
        assert connection._session.has_open_turn is False
        trace = connection._session

    tools = [run for name, run in created if name == "lookup_weather"]
    assert len(tools) == 1
    assert tools[0].run_type == "tool"
    assert tools[0].inputs == {"args": {"city": "Paris"}}
    assert tools[0].outputs == {"content": '{"temperature": 21}'}
    assert tools[0].error is None

    expected_messages = [
        {"role": "user", "content": "Weather in Paris?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "lookup_weather",
                        "arguments": '{"city":"Paris"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "lookup_weather",
            "content": '{"temperature": 21}',
        },
        {"role": "assistant", "content": "It is 21 degrees."},
    ]
    assert trace.messages == expected_messages
    assert trace.run.outputs == {"messages": expected_messages}
    turns = [run for name, run in created if name == "turn"]
    assert len(turns) == 1
    assert turns[0].inputs == {"messages": [expected_messages[0]]}
    assert turns[0].outputs == {"messages": expected_messages[1:]}
    turn_metadata = (turns[0].extra or {}).get("metadata") or {}
    assert turn_metadata["deepgram_ttt_tool_latency_ms"] == 100
    assert len([run for name, run in created if name == "AgentThinking"]) == 1


async def test_tool_cancellation_marks_span_error(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        _frame(
            "FunctionCallRequest",
            functions=[
                {
                    "id": "call-1",
                    "name": "lookup_weather",
                    "arguments": "not-json",
                    "client_side": True,
                }
            ],
        ),
        _frame(
            "FunctionCallCancelled",
            functions=[{"id": "call-1", "name": "lookup_weather"}],
        ),
    ]
    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass

    tools = [run for name, run in created if name == "lookup_weather"]
    assert len(tools) == 1
    assert tools[0].inputs == {"args": "not-json"}
    assert tools[0].error == "function call cancelled by Deepgram"


async def test_error_event_and_body_exception_are_recorded(monkeypatch):
    created = _spy_children(monkeypatch)
    with pytest.raises(ValueError, match="application failed"):
        async with wrap_deepgram_voice(
            FakeConnection([_frame("Error", description="provider failed")])
        ) as connection:
            await connection.recv()
            trace = connection._session
            raise ValueError("application failed")

    errors = [run for name, run in created if name == "Error"]
    assert len(errors) == 1
    assert errors[0].error == "provider failed"
    assert trace.run.error == "ValueError: application failed"


async def test_audio_recording_is_bounded():
    async with wrap_deepgram_voice(
        FakeConnection([]), sample_rate=10, max_audio_seconds=0.1
    ) as connection:
        connection.record_user_audio(b"\x00\x00\x01\x00")
        connection.record_agent_audio(b"\x00\x00\x01\x00")
        trace = connection._session

    assert trace._user_bytes == 2
    assert trace._agent_bytes == 2
    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["audio_truncated"] is True
