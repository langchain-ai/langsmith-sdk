"""Unit tests for raw Gemini Live session tracing."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace as NS
from unittest import mock

import pytest

from langsmith import Client
from langsmith._internal.voice import session as session_mod
from langsmith.integrations.gemini_live import _session as live_mod
from langsmith.integrations.gemini_live._session import (
    _append_transcript,
    _LiveMessageView,
    usage_metadata_from_message,
    wrap_gemini_live,
)

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


class FakeSession:
    """Small stand-in for ``google.genai.live.AsyncSession``."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.session_id = "provider-session"
        self.sent_tool_responses = []

    async def receive(self):
        for message in self._messages:
            yield message

    async def send_tool_response(self, *, function_responses):
        self.sent_tool_responses.append(function_responses)


def _message(
    *,
    user=None,
    user_finished=True,
    agent=None,
    agent_finished=True,
    calls=None,
    interrupted=False,
    turn_complete=False,
    usage=None,
):
    content = None
    if user is not None or agent is not None or interrupted or turn_complete:
        content = NS(
            input_transcription=(
                NS(text=user, finished=user_finished) if user is not None else None
            ),
            output_transcription=(
                NS(text=agent, finished=agent_finished) if agent is not None else None
            ),
            interrupted=interrupted,
            turn_complete=turn_complete,
        )
    tool_call = NS(function_calls=calls) if calls is not None else None
    return NS(
        server_content=content,
        tool_call=tool_call,
        tool_call_cancellation=None,
        usage_metadata=usage,
        model_dump=lambda: {
            "server_content": {"audio": b"\x00\x01"} if content else None
        },
    )


class TestHelpers:
    def test_message_view(self):
        call = NS(id="call-1", name="lookup_weather", args={"city": "Paris"})
        message = _message(
            user="weather?",
            agent="Sunny.",
            calls=[call],
            interrupted=True,
            turn_complete=True,
        )
        view = _LiveMessageView(message)
        assert view.user_transcript == "weather?"
        assert view.user_transcript_finished is True
        assert view.agent_transcript == "Sunny."
        assert view.function_calls == [call]
        assert view.interrupted is True
        assert view.turn_complete is True

    def test_tool_call_cancellation_view(self):
        message = _message()
        message.tool_call_cancellation = NS(ids=["call-1", "call-2"])
        assert _LiveMessageView(message).cancelled_tool_call_ids == [
            "call-1",
            "call-2",
        ]

    def test_unfinished_transcription_is_ignored(self):
        message = _message(user="partial", user_finished=False)
        assert _LiveMessageView(message).user_transcript == "partial"
        assert _LiveMessageView(message).user_transcript_finished is False

    def test_append_transcript_supports_deltas_repetition_and_cap(self):
        assert _append_transcript("Hello ", "world") == "Hello world"
        assert _append_transcript("ha", "ha") == "haha"
        assert len(_append_transcript("", "x" * 3_000)) == 2_000

    def test_usage_maps_direct_live_fields_and_audio(self):
        usage = NS(
            prompt_token_count=100,
            response_token_count=40,
            total_token_count=140,
            prompt_tokens_details=[NS(modality="AUDIO", token_count=80)],
            response_tokens_details=[NS(modality=NS(value="AUDIO"), token_count=30)],
            cached_content_token_count=10,
            thoughts_token_count=4,
        )
        assert usage_metadata_from_message(_message(usage=usage)) == {
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
            "input_token_details": {"audio": 80, "cache_read": 10},
            "output_token_details": {"audio": 30, "reasoning": 4},
        }

    def test_usage_falls_back_to_candidates_fields(self):
        usage = NS(
            prompt_token_count=3,
            response_token_count=None,
            candidates_token_count=2,
            total_token_count=5,
            prompt_tokens_details=None,
            response_tokens_details=None,
            candidates_tokens_details=None,
            cached_content_token_count=None,
            thoughts_token_count=None,
        )
        assert usage_metadata_from_message(_message(usage=usage)) == {
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }

    def test_no_usage(self):
        assert usage_metadata_from_message(_message()) is None


def _spy_children(monkeypatch):
    created = []
    real = session_mod.RunTree.create_child

    def spy(self, **kwargs):
        child = real(self, **kwargs)
        created.append((kwargs.get("name"), child))
        return child

    monkeypatch.setattr(session_mod.RunTree, "create_child", spy)
    return created


class TestWrapper:
    def test_import_does_not_load_google_genai(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "import langsmith.integrations.gemini_live; "
                    "assert not any(name == 'google.genai' or "
                    "name.startswith('google.genai.') for name in sys.modules)"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    async def test_proxy_is_transparent_and_tracing_is_fail_open(self, monkeypatch):
        messages = [_message(user="hello"), _message(turn_complete=True)]
        raw = FakeSession(messages)
        monkeypatch.setattr(
            live_mod._GeminiLiveTracer,
            "observe",
            mock.Mock(side_effect=RuntimeError("broken tracer")),
        )
        seen = []
        response = {"id": "call-1", "name": "tool", "response": {"answer": 42}}
        async with wrap_gemini_live(raw) as session:
            assert session.session_id == "provider-session"
            assert await session.send_tool_response(function_responses=response) is None
            async for message in session.receive():
                seen.append(message)
        assert seen == messages
        assert raw.sent_tool_responses == [response]

    async def test_transcript_usage_llm_and_markers(self, monkeypatch):
        created = _spy_children(monkeypatch)
        usage = NS(
            prompt_token_count=8,
            response_token_count=5,
            total_token_count=13,
            prompt_tokens_details=None,
            response_tokens_details=None,
            cached_content_token_count=None,
            thoughts_token_count=None,
        )
        messages = [
            _message(user="what is ", user_finished=False),
            _message(user="the weather?", user_finished=False),
            _message(agent="It is ", agent_finished=False),
            _message(agent="sunny.", agent_finished=False),
            _message(turn_complete=True, usage=usage),
        ]
        async with wrap_gemini_live(
            FakeSession(messages), model="gemini-live", thread_id="thread-1"
        ) as session:
            async for _ in session.receive():
                pass
            trace = session._trace

        assert trace.messages == [
            {"role": "user", "content": "what is the weather?"},
            {"role": "assistant", "content": "It is sunny."},
        ]
        assert trace.run.name == "what is the weather?"
        assert trace.run.outputs == {"messages": trace.messages}
        root_metadata = (trace.run.extra or {}).get("metadata") or {}
        assert root_metadata["ls_integration"] == "gemini-live"

        llms = [child for name, child in created if name == "turn_complete"]
        assert len(llms) == 1
        assert llms[0].run_type == "llm"
        assert llms[0].outputs == {"role": "assistant", "content": "It is sunny."}
        assert "usage_metadata" not in llms[0].outputs
        llm_metadata = (llms[0].extra or {}).get("metadata") or {}
        assert llm_metadata["usage_metadata"] == {
            "input_tokens": 8,
            "output_tokens": 5,
            "total_tokens": 13,
        }
        assert llm_metadata["ls_provider"] == "google"
        assert llm_metadata["ls_model_name"] == "gemini-live"
        assert [name for name, _ in created].count("output_transcription") == 0

    async def test_function_call_span_and_interruption(self, monkeypatch):
        created = _spy_children(monkeypatch)
        call = NS(id="call-1", name="lookup_weather", args={"city": "Tokyo"})
        response = NS(
            id="call-1",
            name="lookup_weather",
            response={"city": "Tokyo", "condition": "sunny"},
        )

        messages = [
            _message(calls=[call]),
            _message(interrupted=True),
        ]
        async with wrap_gemini_live(
            FakeSession(messages), is_agent_speaking=lambda: True
        ) as session:
            async for message in session.receive():
                if message.tool_call:
                    await session.send_tool_response(function_responses=response)
            trace = session._trace

        tool_runs = [child for name, child in created if name == "lookup_weather"]
        assert len(tool_runs) == 1
        assert tool_runs[0].run_type == "tool"
        assert tool_runs[0].parent_run_id == trace.run.id
        assert tool_runs[0].inputs == {"args": {"city": "Tokyo"}}
        assert tool_runs[0].outputs == {
            "response": {"city": "Tokyo", "condition": "sunny"}
        }
        tool_metadata = (tool_runs[0].extra or {}).get("metadata") or {}
        assert tool_metadata["function_call_id"] == "call-1"
        interrupted = [child for name, child in created if name == "interrupted"]
        assert len(interrupted) == 1
        metadata = (interrupted[0].extra or {}).get("metadata") or {}
        assert metadata["was_audible"] is True

    async def test_parallel_tool_calls_are_matched_by_id(self, monkeypatch):
        created = _spy_children(monkeypatch)
        calls = [
            NS(id="call-1", name="first", args={"value": 1}),
            NS(id="call-2", name="second", args={"value": 2}),
        ]
        responses = [
            {"id": "call-2", "name": "second", "response": {"result": 2}},
            {"id": "call-1", "name": "first", "response": {"result": 1}},
        ]

        async with wrap_gemini_live(FakeSession([_message(calls=calls)])) as session:
            async for _ in session.receive():
                pass
            await session.send_tool_response(function_responses=responses)

        tools = {name: child for name, child in created if name in {"first", "second"}}
        assert tools["first"].outputs == {"response": {"result": 1}}
        assert tools["second"].outputs == {"response": {"result": 2}}

    async def test_incomplete_tool_call_is_closed_with_error(self, monkeypatch):
        created = _spy_children(monkeypatch)
        call = NS(id="call-1", name="lookup_weather", args={"city": "Tokyo"})

        async with wrap_gemini_live(FakeSession([_message(calls=[call])])) as session:
            async for _ in session.receive():
                pass

        tool_runs = [child for name, child in created if name == "lookup_weather"]
        assert len(tool_runs) == 1
        assert tool_runs[0].error == "tool did not complete before the session ended"

    async def test_audio_is_bounded_and_replicas_propagate(self, monkeypatch):
        created = _spy_children(monkeypatch)
        replicas = [{"project_name": "replica"}]
        async with wrap_gemini_live(
            FakeSession([_message(user="hi")]),
            sample_rate=10,
            max_audio_seconds=1.0,
            replicas=replicas,
        ) as session:
            session.record_user_audio(b"\x00" * 16)
            session.record_user_audio(b"\x00" * 16)
            async for _ in session.receive():
                pass
            trace = session._trace

        assert trace.max_audio_bytes == 20
        assert sum(len(chunk) for _, chunk in trace.user_chunks) == 20
        assert trace._audio_truncated is True
        assert trace.run.replicas == replicas
        input_runs = [child for name, child in created if name == "input_transcription"]
        assert input_runs and input_runs[0].replicas == replicas

    async def test_body_error_is_recorded_and_propagated(self):
        context = wrap_gemini_live(FakeSession([]))
        with pytest.raises(RuntimeError, match="application failed"):
            async with context as session:
                trace = session._trace
                raise RuntimeError("application failed")
        assert trace.run.error == "RuntimeError: application failed"
