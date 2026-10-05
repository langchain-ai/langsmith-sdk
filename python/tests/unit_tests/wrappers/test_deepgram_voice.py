"""Unit tests for Deepgram Voice Agent WebSocket tracing."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
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


class FakePydanticV1Message:
    """Deepgram supports Pydantic v1, whose models expose ``dict`` only."""

    def __init__(self, **value):
        self.value = value

    def dict(self, *, exclude_none):
        assert exclude_none is True
        return self.value


class FakeSdkConnection:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent_settings = []
        self.sent_function_responses = []
        self.sent_media = []
        self.sent_updates = []
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

    async def send_update_listen(self, message):
        self.sent_updates.append(message)

    async def send_update_think(self, message):
        self.sent_updates.append(message)

    async def send_update_speak(self, message):
        self.sent_updates.append(message)


class FakeListenerConnection:
    """Official-SDK-shaped callback connection used by ``start_listening``."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.callbacks = {}

    def on(self, event, callback):
        self.callbacks.setdefault(event, []).append(callback)

    async def start_listening(self):
        for frame in self.frames:
            for callback in self.callbacks.get("message", []):
                callback(frame)


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


def test_import_loads_deepgram_without_websockets():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import langsmith.integrations.deepgram_voice; "
                "assert 'websockets' not in sys.modules; "
                "assert 'deepgram' in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_public_wrapper_emits_beta_warning():
    from langsmith._internal._beta_decorator import (
        LangSmithBetaWarning,
        _warn_once,
    )

    _warn_once.cache_clear()
    with pytest.warns(LangSmithBetaWarning, match="wrap_deepgram_voice"):
        wrap_deepgram_voice(FakeConnection([]))


def test_pydantic_v1_messages_are_normalized():
    message = FakePydanticV1Message(type="Welcome", request_id="request-1")
    assert voice_mod._normalize_deepgram_frame(message) == {
        "type": "Welcome",
        "request_id": "request-1",
    }


@pytest.mark.parametrize("frame", ["not-json", "[]", '{"missing":"type"}'])
def test_malformed_messages_are_ignored(frame):
    assert voice_mod._normalize_deepgram_frame(frame) is None


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


async def test_official_sdk_start_listening_path_is_traced():
    raw = FakeListenerConnection(
        [
            FakePydanticV1Message(type="Welcome", request_id="request-listener"),
            FakePydanticV1Message(
                type="ConversationText", role="user", content="listener question"
            ),
        ]
    )
    seen = []

    async with wrap_deepgram_voice(raw) as connection:
        connection.on("message", seen.append)
        await connection.start_listening()
        trace = connection._session

    assert seen == raw.frames
    assert trace.messages == [{"role": "user", "content": "listener question"}]
    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["deepgram_request_id"] == "request-listener"


async def test_direct_anext_lazily_initializes_iterator():
    raw = FakeConnection([_frame("Welcome", request_id="request-direct-next")])

    async with wrap_deepgram_voice(raw) as connection:
        assert await connection.__anext__() == raw.frames[0]
        trace = connection._session

    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["deepgram_request_id"] == "request-direct-next"


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


async def test_raw_dict_latency_report_is_ignored_and_returned_unchanged(monkeypatch):
    created = _spy_children(monkeypatch)
    latency_report = {"type": "LatencyReport", "total_latency": 0.42}
    frames = [
        FakeSdkMessage(type="UserStartedSpeaking"),
        FakeSdkMessage(type="ConversationText", role="user", content="Hello"),
        FakeSdkMessage(type="ConversationText", role="assistant", content="Hi"),
        FakeSdkMessage(type="AgentAudioDone"),
        latency_report,
    ]
    raw = FakeSdkConnection(frames)
    seen = []

    async with wrap_deepgram_voice(raw) as connection:
        async for frame in connection:
            seen.append(frame)

    assert seen == frames
    assert seen[-1] is latency_report
    assert not any(name == "LatencyReport" for name, _ in created)


async def test_dynamic_model_updates_refresh_root_metadata():
    raw = FakeSdkConnection([])
    updates = [
        FakeSdkMessage(
            type="UpdateListen",
            listen={"provider": {"type": "deepgram", "model": "nova-4"}},
        ),
        FakeSdkMessage(
            type="UpdateThink",
            think={"provider": {"type": "anthropic", "model": "claude-next"}},
        ),
        FakeSdkMessage(
            type="UpdateSpeak",
            speak={"provider": {"type": "deepgram", "model": "aura-next"}},
        ),
    ]

    async with wrap_deepgram_voice(raw) as connection:
        await connection.send_update_listen(updates[0])
        await connection.send_update_think(updates[1])
        await connection.send_update_speak(updates[2])
        trace = connection._session

    assert raw.sent_updates == updates
    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["deepgram_listen_model"] == "nova-4"
    assert metadata["deepgram_think_provider"] == "anthropic"
    assert metadata["deepgram_think_model"] == "claude-next"
    assert metadata["deepgram_speak_model"] == "aura-next"


async def test_provider_update_events_are_recorded(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        FakeSdkMessage(type="PromptUpdated"),
        FakeSdkMessage(type="SpeakUpdated"),
        FakeSdkMessage(type="ThinkUpdated"),
    ]

    async with wrap_deepgram_voice(FakeSdkConnection(frames)) as connection:
        async for _ in connection:
            pass

    for event_type in ("PromptUpdated", "SpeakUpdated", "ThinkUpdated"):
        event = next(run for name, run in created if name == event_type)
        assert event.outputs == {"type": event_type}


async def test_root_context_and_integration_version(monkeypatch):
    contexts = []

    @contextmanager
    def capture_context(**kwargs):
        contexts.append(kwargs)
        yield

    monkeypatch.setattr(voice_mod, "tracing_context", capture_context)
    monkeypatch.setattr(voice_mod, "get_package_version", lambda _: "7.2.0")

    async with wrap_deepgram_voice(FakeConnection([])) as connection:
        trace = connection._session

    assert contexts[0]["parent"] is trace.run
    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["ls_integration_version"] == "7.2.0"


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
    assert turns[0].inputs == {}
    assert turns[0].outputs == {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
    }

    names = [name for name, _ in created]
    assert not {"user_message", "model", "agent_audio"}.intersection(names)
    assert not {
        "Welcome",
        "LatencyReport",
        "SettingsApplied",
        "UserStartedSpeaking",
    }.intersection(names)


async def test_latency_report_is_ignored_while_turn_is_open(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        _frame("UserStartedSpeaking"),
        _frame("ConversationText", role="user", content="first question"),
        _frame("ConversationText", role="assistant", content="first answer"),
        _frame("AgentAudioDone"),
        _frame("UserStartedSpeaking"),
        _frame("ConversationText", role="user", content="second question"),
        _frame("LatencyReport", total_latency=0.42),
        _frame("ConversationText", role="assistant", content="second answer"),
        _frame("AgentAudioDone"),
    ]

    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass

    turns = [run for name, run in created if name == "turn"]
    assert len(turns) == 2
    assert not any(name == "LatencyReport" for name, _ in created)


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
        _frame("LatencyReport", total_latency=0.64),
        _frame("ConversationText", role="user", content="second question"),
    ]
    async with wrap_deepgram_voice(
        FakeConnection(frames), is_agent_speaking=lambda: True
    ) as connection:
        async for _ in connection:
            pass
        trace = connection._session

    assert not any(name == "agent_audio" for name, _ in created)
    assert len([run for name, run in created if name == "AgentAudioDone"]) == 1

    turns = [run for name, run in created if name == "turn"]
    assert len(turns) == 2
    assert turns[0].inputs == {}
    assert turns[0].outputs == {
        "messages": [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "long answer"},
        ]
    }
    first_turn_metadata = (turns[0].extra or {}).get("metadata") or {}
    assert first_turn_metadata["was_interrupted"] is True
    assert turns[1].inputs == {}
    assert turns[1].outputs == {
        "messages": [{"role": "user", "content": "second question"}]
    }
    audio_done = next(run for name, run in created if name == "AgentAudioDone")
    assert audio_done.parent_run_id == trace.run.id
    audio_done_metadata = (audio_done.extra or {}).get("metadata") or {}
    assert audio_done_metadata["interrupted_completion"] is True
    assert not any(name == "LatencyReport" for name, _ in created)


async def test_history_is_summarized_on_root_without_a_span(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        FakeSdkMessage(type="History", role="user", content="private prior input"),
        FakeSdkMessage(
            type="History",
            function_calls=[
                {
                    "id": "private-call",
                    "name": "private-tool",
                    "arguments": '{"secret":"private prior input"}',
                }
            ],
        ),
    ]
    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass
        trace = connection._session

    metadata = (trace.run.extra or {}).get("metadata") or {}
    assert metadata["deepgram_history_message_count"] == 2
    assert not any(name == "History" for name, _ in created)
    assert "private prior input" not in repr(metadata)
    assert "private-tool" not in repr(metadata)


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
    assert turns[0].inputs == {}
    assert turns[0].outputs == {"messages": expected_messages}
    assert not any(name == "LatencyReport" for name, _ in created)
    assert len([run for name, run in created if name == "AgentThinking"]) == 1


async def test_idless_server_tool_response_matches_unique_name(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        _frame(
            "FunctionCallRequest",
            functions=[
                {
                    "id": "call-server",
                    "name": "lookup_weather",
                    "arguments": '{"city":"Paris"}',
                    "client_side": False,
                }
            ],
        ),
        _frame(
            "FunctionCallResponse",
            name="lookup_weather",
            content='{"temperature": 21}',
        ),
    ]

    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass
        trace = connection._session

    tool = next(run for name, run in created if name == "lookup_weather")
    assert tool.outputs == {"content": '{"temperature": 21}'}
    assert tool.error is None
    assert trace.messages[-1] == {
        "role": "tool",
        "tool_call_id": "call-server",
        "name": "lookup_weather",
        "content": '{"temperature": 21}',
    }


async def test_ambiguous_idless_tool_response_is_not_misattributed(monkeypatch):
    created = _spy_children(monkeypatch)
    frames = [
        _frame(
            "FunctionCallRequest",
            functions=[
                {
                    "id": "call-1",
                    "name": "lookup_weather",
                    "arguments": '{"city":"Paris"}',
                    "client_side": False,
                },
                {
                    "id": "call-2",
                    "name": "lookup_weather",
                    "arguments": '{"city":"London"}',
                    "client_side": False,
                },
            ],
        ),
        _frame(
            "FunctionCallResponse",
            name="lookup_weather",
            content='{"temperature": 21}',
        ),
    ]

    async with wrap_deepgram_voice(FakeConnection(frames)) as connection:
        async for _ in connection:
            pass
        trace = connection._session

    open_tools = [run for name, run in created if name == "lookup_weather"]
    assert len(open_tools) == 2
    assert all(
        run.error == "function did not complete before the session ended"
        for run in open_tools
    )
    unmatched = next(run for name, run in created if name == "FunctionCallResponse")
    unmatched_metadata = (unmatched.extra or {}).get("metadata") or {}
    assert unmatched_metadata["unmatched_tool_response"] is True
    assert not any(message.get("role") == "tool" for message in trace.messages)


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
