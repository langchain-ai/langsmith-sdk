"""Unit tests for the OpenAI Realtime raw-connection wrapper (``_connection.py``).

Covers the pure payload-shaping helpers, the fail-open guard around the tracer,
and an end-to-end pass of a fake Realtime event stream through ``wrap_realtime``
(turn grouping, transcript rollup, first-audio latency, barge-in) — all against a
mocked client so nothing hits the network.
"""

from __future__ import annotations

from types import SimpleNamespace as NS
from unittest import mock

import pytest

from langsmith import Client
from langsmith._internal.voice import session as session_mod
from langsmith._internal.voice.helpers import observe_safely
from langsmith.integrations.openai_realtime import _connection as conn_mod
from langsmith.integrations.openai_realtime._connection import (
    is_inbound,
    response_assistant_output,
    response_usage_metadata,
    wrap_realtime,
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


class FakeConnection:
    """Minimal stand-in for an ``AsyncRealtimeConnection``: async-iterates events."""

    def __init__(self, events):
        self._events = list(events)
        self._it = None

    def __aiter__(self):
        self._it = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _response_done(text, *, tool=None, usage=None, status="completed"):
    content = [NS(type="audio", transcript=text, text=None)] if text else []
    output = [NS(type="message", content=content)]
    if tool:
        output.append(
            NS(
                type="function_call",
                name=tool["name"],
                arguments=tool["args"],
                call_id=tool["id"],
            )
        )
    response = NS(output=output, usage=usage, status=status)
    return NS(type="response.done", response=response)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


class TestHelpers:
    def test_is_inbound(self):
        assert is_inbound("input_audio_buffer.speech_started") is True
        assert is_inbound("conversation.item.input_audio_transcription.completed")
        assert is_inbound("response.done") is False
        assert is_inbound("response.output_audio.delta") is False

    def test_response_assistant_output_text_and_tools(self):
        ev = _response_done(
            "hello there",
            tool={"name": "lookup", "args": '{"q": "x"}', "id": "call_1"},
        )
        out = response_assistant_output(ev.response)
        assert out["role"] == "assistant"
        assert out["content"] == "hello there"
        # OpenAI ChatCompletion shape so the LangSmith UI renders the tool call
        # inline on the model span (a flat {name, args, id} spills to "Additional
        # Fields"). ``arguments`` stays the raw wire JSON string.
        assert out["tool_calls"] == [
            {
                "id": "call_1",
                "type": "function",
                "index": 0,
                "function": {"name": "lookup", "arguments": '{"q": "x"}'},
            }
        ]

    def test_response_assistant_output_arguments_passthrough(self):
        # Arguments are forwarded verbatim (the UI parses them); missing → "{}".
        ev = _response_done("", tool={"name": "t", "args": None, "id": "c"})
        out = response_assistant_output(ev.response)
        assert out["tool_calls"][0]["function"]["arguments"] == "{}"

    def test_response_usage_metadata_maps_tokens(self):
        usage = NS(input_tokens=10, output_tokens=5, total_tokens=None)
        md = response_usage_metadata(NS(usage=usage))
        # Shared mapper always includes (possibly empty) detail blocks.
        assert md == {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_token_details": {},
            "output_token_details": {},
        }

    def test_response_usage_metadata_captures_audio_and_cache_detail(self):
        # Realtime spells detail blocks ``*_token_details`` (singular); the mapper
        # should still surface audio / cached-token detail via the shared shape.
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {"audio_tokens": 80, "cached_tokens": 20},
            "output_token_details": {"audio_tokens": 40},
        }
        md = response_usage_metadata(NS(usage=usage))
        assert md["input_token_details"]["audio"] == 80
        assert md["input_token_details"]["cache_read"] == 20
        assert md["output_token_details"]["audio"] == 40

    def test_response_usage_metadata_none_when_absent(self):
        assert response_usage_metadata(NS(usage=None)) is None
        assert (
            response_usage_metadata(
                NS(usage=NS(input_tokens=None, output_tokens=None, total_tokens=None))
            )
            is None
        )


# --------------------------------------------------------------------------- #
# Fail-open
# --------------------------------------------------------------------------- #


class TestFailOpen:
    def test_observe_safely_swallows(self):
        observe = mock.Mock(side_effect=RuntimeError("boom"))
        # Must not raise.
        observe_safely(observe, NS(type="whatever"))

    async def test_broken_tracer_does_not_break_the_loop(self, monkeypatch):
        events = [NS(type="session.created"), NS(type="x"), NS(type="y")]
        # Every observe call blows up; the caller must still receive every event.
        monkeypatch.setattr(
            conn_mod._RealtimeTracer,
            "observe",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        seen = []
        async with wrap_realtime(FakeConnection(events)) as connection:
            async for event in connection:
                seen.append(event.type)
        assert seen == ["session.created", "x", "y"]

    async def test_event_without_type_is_skipped(self):
        # An object with no ``.type`` must not raise out of the loop.
        events = [object(), NS(type="session.created")]
        seen = []
        async with wrap_realtime(FakeConnection(events)) as connection:
            async for event in connection:
                seen.append(event)
        assert len(seen) == 2


# --------------------------------------------------------------------------- #
# End-to-end trace shape
# --------------------------------------------------------------------------- #


def _spy_children(monkeypatch):
    """Capture every child span created on any RunTree during the test."""
    created = []
    real = session_mod.RunTree.create_child

    def spy(self, **kwargs):
        child = real(self, **kwargs)
        created.append((kwargs.get("name"), child))
        return child

    monkeypatch.setattr(session_mod.RunTree, "create_child", spy)
    return created


class TestEndToEnd:
    async def test_single_turn_transcript_latency_and_llm(self, monkeypatch):
        created = _spy_children(monkeypatch)
        usage = NS(input_tokens=3, output_tokens=4, total_tokens=7)
        events = [
            NS(type="session.created"),
            NS(type="input_audio_buffer.speech_started"),
            NS(type="input_audio_buffer.speech_stopped"),
            NS(
                type="conversation.item.input_audio_transcription.completed",
                transcript="what's the weather?",
            ),
            NS(type="response.output_audio.delta", delta=b"\x00\x00"),
            NS(type="response.output_audio_transcript.done", transcript="It's sunny."),
            _response_done("It's sunny.", usage=usage),
        ]
        async with wrap_realtime(FakeConnection(events), thread_id="t") as connection:
            async for _ in connection:
                pass
            session = connection._session

        # Transcript rollup carries both sides.
        assert session.messages == [
            {"role": "user", "content": "what's the weather?"},
            {"role": "assistant", "content": "It's sunny."},
        ]
        # First user utterance named the trace (the root run's display name).
        assert session.run.name == "what's the weather?"

        # The root is attributed to the raw-Realtime-API integration.
        root_meta = (session.run.extra or {}).get("metadata") or {}
        assert root_meta["ls_integration"] == "openai-realtime"

        # Exactly one turn, and first-audio latency was timed onto it.
        turns = [child for name, child in created if name == "turn"]
        assert len(turns) == 1
        turn_meta = (turns[0].extra or {}).get("metadata") or {}
        assert "latency_to_first_audio_ms" in turn_meta

        # An llm span recorded the assistant message.
        llms = [child for name, child in created if name == "model"]
        assert len(llms) == 1
        assert llms[0].outputs == {"role": "assistant", "content": "It's sunny."}

    async def test_barge_in_flags_interrupted_turn(self, monkeypatch):
        created = _spy_children(monkeypatch)
        events = [
            NS(type="input_audio_buffer.speech_started"),  # turn 1 opens
            NS(
                type="conversation.item.input_audio_transcription.completed",
                transcript="first",
            ),
            NS(type="input_audio_buffer.speech_started"),  # turn 2 — interrupts 1
            NS(
                type="conversation.item.input_audio_transcription.completed",
                transcript="second",
            ),
        ]
        # Agent is "still audible" → the second speech_started is a barge-in.
        async with wrap_realtime(
            FakeConnection(events), is_agent_speaking=lambda: True
        ) as connection:
            async for _ in connection:
                pass

        turns = [child for name, child in created if name == "turn"]
        assert len(turns) == 2
        meta_first = (turns[0].extra or {}).get("metadata") or {}
        assert meta_first.get("was_interrupted") is True

    async def test_max_audio_seconds_bounds_recording(self):
        async with wrap_realtime(
            FakeConnection([]), sample_rate=10, max_audio_seconds=1.0
        ) as connection:
            # cap = 1.0s * 10 * 2 = 20 bytes per channel.
            connection.record_user_audio(b"\x00" * 16)  # under cap → kept
            connection.record_user_audio(b"\x00" * 16)  # over cap → kept (pushes over)
            connection.record_user_audio(b"\x00" * 16)  # dropped
            session = connection._session
        assert session.max_audio_bytes == 20
        assert len(session.user_chunks) == 2
        assert session._audio_truncated is True

    async def test_replicas_propagate_to_root_and_children(self, monkeypatch):
        created = _spy_children(monkeypatch)
        replicas = [{"project_name": "replica-project"}]
        # A speech_started event opens a "turn" child under the root.
        events = [NS(type="input_audio_buffer.speech_started")]
        async with wrap_realtime(
            FakeConnection(events), replicas=replicas
        ) as connection:
            async for _ in connection:
                pass
            session = connection._session

        # The root carries the replicas...
        assert session.run.replicas == [{"project_name": "replica-project"}]
        # ...and child spans inherit them via create_child.
        turns = [child for name, child in created if name == "turn"]
        assert turns and turns[0].replicas == [{"project_name": "replica-project"}]
