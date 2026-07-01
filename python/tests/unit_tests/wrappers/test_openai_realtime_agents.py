"""Unit tests for the OpenAI Agents-SDK realtime wrapper (``_session.py``).

Three layers: the pure event-shaping helpers (``_clean``, ``describe_event``, …),
the ``_AgentsRealtimeTracer`` that reconstructs the conversation from ``history``
snapshots (partial collapse, turn grouping, hold-last flushing, tool/barge-in
spans), and the ``wrap_realtime_session`` proxy (delegation, fail-open). All run
against a mocked client so nothing hits the network.
"""

from __future__ import annotations

from types import SimpleNamespace as NS
from unittest import mock

import pytest

from langsmith import Client
from langsmith._internal.voice import session as voice_session_mod
from langsmith._internal.voice.session import EventSession, start_session
from langsmith.integrations.openai_realtime import _session as agents_mod
from langsmith.integrations.openai_realtime._session import (
    _AgentsRealtimeTracer,
    _clean,
    _item_text,
    _stringify,
    describe_event,
    raw_input_transcript,
    wrap_realtime_session,
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


def _item(iid, role, text):
    """A realtime history item: id, role, and one content part."""
    content = [NS(transcript=text, text=None)] if text else []
    return NS(item_id=iid, role=role, content=content)


def _history_updated(*items):
    return NS(type="history_updated", history=list(items))


def _spy_children(monkeypatch):
    """Capture (name, child) for every span created on any RunTree."""
    created = []
    real = voice_session_mod.RunTree.create_child

    def spy(self, **kwargs):
        child = real(self, **kwargs)
        created.append((kwargs.get("name"), child))
        return child

    monkeypatch.setattr(voice_session_mod.RunTree, "create_child", spy)
    return created


# --------------------------------------------------------------------------- #
# Pure shaping helpers
# --------------------------------------------------------------------------- #


class TestCleanAndShape:
    def test_clean_bytes_private_circular_and_width(self):
        assert _clean(b"abcd") == "<4 bytes>"
        # Private keys are dropped.
        assert _clean({"a": 1, "_secret": 2}) == {"a": 1}
        # Cycles are broken, not followed.
        d: dict = {}
        d["self"] = d
        assert _clean(d) == {"self": "<circular>"}
        # Wide collections are capped with a "+N more" marker.
        out = _clean(list(range(60)))
        assert len(out) == 51
        assert out[:3] == [0, 1, 2]
        assert out[-1] == "… +10 more"

    def test_stringify(self):
        assert _stringify(5) == 5
        assert _stringify("x") == "x"
        assert _stringify([1, 2]) == [1, 2]
        assert _stringify(object()).startswith("<")  # exotic → repr

    def test_item_text_joins_content_parts(self):
        item = _item("i", "user", None)
        item.content = [
            NS(transcript="hello", text=None),
            NS(transcript=None, text="world"),
        ]
        assert _item_text(item) == ("user", "hello world")
        assert _item_text(None) == (None, None)
        assert _item_text(_item("i", "assistant", None)) == ("assistant", None)

    def test_raw_input_transcript(self):
        ev = NS(
            data=NS(
                type="input_audio_transcription_completed",
                transcript="  hi there  ",
                item_id="u1",
            )
        )
        assert raw_input_transcript(ev) == ("u1", "hi there")
        # Wrong wrapped type, or empty transcript → None.
        assert raw_input_transcript(NS(data=NS(type="other"))) is None
        assert (
            raw_input_transcript(
                NS(data=NS(type="input_audio_transcription_completed", transcript=" "))
            )
            is None
        )

    def test_describe_event_variants(self):
        name, payload, inbound = describe_event(
            NS(type="tool_start", tool=NS(name="lookup"), arguments='{"q": 1}')
        )
        assert name == "tool_start"
        assert inbound is True  # a tool call is the model's request → input
        assert payload["tool"] == "lookup"

        _, payload, inbound = describe_event(
            NS(type="tool_end", tool=NS(name="lookup"), arguments="{}", output="sunny")
        )
        assert payload["output"] == "sunny"
        assert inbound is False

        _, payload, inbound = describe_event(
            NS(type="history_added", item=_item("u", "user", "hi"))
        )
        assert (payload["role"], payload["text"]) == ("user", "hi")
        assert inbound is True

        _, payload, _ = describe_event(NS(type="error", error="boom"))
        assert payload["error"] == "boom"


# --------------------------------------------------------------------------- #
# _AgentsRealtimeTracer — conversation reconstruction
# --------------------------------------------------------------------------- #


def _tracer(session, **kwargs):
    return _AgentsRealtimeTracer(session, **kwargs)


class TestTracer:
    def test_history_turn_collapses_partials_and_emits_spans(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # One user turn, then the assistant transcript arrives as growing partials
        # across snapshots — the fold keeps only the final text.
        tracer.observe(_history_updated(_item("u1", "user", "weather?")))
        tracer.observe(NS(type="audio"))  # first audio → latency on the open turn
        tracer.observe(
            _history_updated(
                _item("u1", "user", "weather?"), _item("a1", "assistant", "It's")
            )
        )
        tracer.observe(
            _history_updated(
                _item("u1", "user", "weather?"), _item("a1", "assistant", "It's sunny.")
            )
        )
        tracer.flush_pending()
        session.finalize()

        # Transcript collapsed to one line per side.
        assert session.messages == [
            {"role": "user", "content": "weather?"},
            {"role": "assistant", "content": "It's sunny."},
        ]
        # Exactly one turn / user_message / model span.
        names = [n for n, _ in created]
        assert names.count("turn") == 1
        assert names.count("user_message") == 1
        assert names.count("model") == 1
        model = next(c for n, c in created if n == "model")
        assert model.outputs == {"role": "assistant", "content": "It's sunny."}
        # Latency was timed onto the turn.
        turn = next(c for n, c in created if n == "turn")
        assert "latency_to_first_audio_ms" in (turn.extra or {}).get("metadata", {})

    def test_hold_last_defers_final_message_until_teardown(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # A lone user item is held back (it may still be streaming).
        tracer.observe(_history_updated(_item("u1", "user", "hi")))
        assert session.messages == []
        assert not any(n == "user_message" for n, _ in created)

        # A following assistant item supersedes the user one → user now emits.
        tracer.observe(
            _history_updated(_item("u1", "user", "hi"), _item("a1", "assistant", "yo"))
        )
        assert session.messages == [{"role": "user", "content": "hi"}]
        assert any(n == "user_message" for n, _ in created)
        assert not any(n == "model" for n, _ in created)  # assistant still held

        # Teardown flushes the trailing assistant message.
        tracer.flush_pending()
        assert session.messages[-1] == {"role": "assistant", "content": "yo"}
        assert any(n == "model" for n, _ in created)

    def test_tool_start_and_end_become_one_tool_span(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # A start/end pair collapses to a single tool span named for the tool,
        # carrying the args (in) and output (out). Its duration is the real gap
        # between the two events.
        tracer.observe(
            NS(type="tool_start", tool=NS(name="lookup"), arguments='{"city": "SF"}')
        )
        tracer.observe(
            NS(
                type="tool_end",
                tool=NS(name="lookup"),
                arguments='{"city": "SF"}',
                output="sunny",
            )
        )
        tools = [c for n, c in created if n == "lookup"]
        assert len(tools) == 1  # one span, not a separate start + end
        tool = tools[0]
        assert tool.run_type == "tool"
        assert tool.inputs == {"arguments": '{"city": "SF"}'}
        assert tool.outputs == {"output": "sunny"}

    def test_tool_end_without_start_falls_back_to_point_in_time(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # tool_end with no matching open start (tracing began mid-call) is still
        # recorded as a tool span.
        tracer.observe(
            NS(
                type="tool_end",
                tool=NS(name="lookup"),
                arguments='{"city": "SF"}',
                output="sunny",
            )
        )
        tool = next(c for n, c in created if n == "lookup")
        assert tool.run_type == "tool"
        assert tool.outputs == {"output": "sunny"}

    def test_orphan_tool_span_closed_with_error_at_teardown(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # A tool_start whose tool never returns (no tool_end) is closed at
        # teardown with an error rather than left dangling open.
        tracer.observe(NS(type="tool_start", tool=NS(name="lookup"), arguments="{}"))
        tool = next(c for n, c in created if n == "lookup")
        assert tool.end_time is None  # still open
        tracer.flush_pending()
        assert tool.end_time is not None  # closed
        assert tool.error

    def test_audio_interrupted_flags_open_turn(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        tracer.observe(_history_updated(_item("u1", "user", "hi")))  # opens a turn
        tracer.observe(NS(type="audio_interrupted", item_id="a1"))
        turn = next(c for n, c in created if n == "turn")
        assert (turn.extra or {}).get("metadata", {}).get("was_interrupted") is True
        assert any(n == "audio_interrupted" for n, _ in created)

    def test_raw_model_event_user_transcript(self, monkeypatch):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        created = _spy_children(monkeypatch)
        tracer = _tracer(session)

        # On a barge-in the user transcript can arrive only as a raw_model_event.
        tracer.observe(
            NS(
                type="raw_model_event",
                data=NS(
                    type="input_audio_transcription_completed",
                    transcript="cancel that",
                    item_id="u1",
                ),
            )
        )
        tracer.flush_pending()
        assert session.messages == [{"role": "user", "content": "cancel that"}]
        assert any(n == "user_message" for n, _ in created)

    def test_on_message_called_once_per_finalized_line(self):
        session = start_session(
            thread_id="t", sample_rate=24_000, integration="openai-agents-realtime"
        )
        seen: list = []
        tracer = _tracer(
            session, on_message=lambda role, text: seen.append((role, text))
        )

        # The same finalized messages reappear across snapshots; each fires once.
        tracer.observe(_history_updated(_item("u1", "user", "hi")))
        tracer.observe(
            _history_updated(
                _item("u1", "user", "hi"), _item("a1", "assistant", "hello")
            )
        )
        tracer.observe(
            _history_updated(
                _item("u1", "user", "hi"), _item("a1", "assistant", "hello")
            )
        )
        tracer.flush_pending()
        assert seen == [("user", "hi"), ("assistant", "hello")]


# --------------------------------------------------------------------------- #
# wrap_realtime_session proxy
# --------------------------------------------------------------------------- #


class FakeSession:
    """Stand-in RealtimeSession: an async context manager that iterates events."""

    def __init__(self, events):
        self._events = list(events)
        self._it = None
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True
        return False

    def __aiter__(self):
        self._it = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    def send_audio(self):
        return "delegated"


class TestProxy:
    async def test_enters_exits_underlying_and_traces(self):
        fake = FakeSession(
            [
                _history_updated(
                    _item("u1", "user", "hi"), _item("a1", "assistant", "yo")
                )
            ]
        )
        async with wrap_realtime_session(fake, thread_id="t") as conn:
            assert fake.entered is True
            assert conn.send_audio() == "delegated"  # attribute delegation
            async for _ in conn:
                pass
            trace = conn._trace
        # Underlying session was exited, and the conversation was traced.
        assert fake.exited is True
        assert trace.messages == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "yo"},
        ]
        # The root is attributed to the Agents SDK realtime backend.
        root_meta = (trace.run.extra or {}).get("metadata") or {}
        assert root_meta["ls_integration"] == "openai-agents-realtime"

    async def test_broken_tracer_does_not_break_loop(self, monkeypatch):
        events = [NS(type="audio"), NS(type="other")]
        monkeypatch.setattr(
            agents_mod._AgentsRealtimeTracer,
            "observe",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        seen = []
        async with wrap_realtime_session(FakeSession(events)) as conn:
            async for event in conn:
                seen.append(event)
        assert len(seen) == 2

    async def test_tracing_setup_failure_unwinds_underlying_session(self, monkeypatch):
        # If our tracing setup raises after the underlying session was entered,
        # __aenter__ must unwind it (Python won't call __aexit__) so it can't leak.
        fake = FakeSession([])
        monkeypatch.setattr(
            agents_mod, "start_session", mock.Mock(side_effect=RuntimeError("boom"))
        )
        with pytest.raises(RuntimeError, match="boom"):
            async with wrap_realtime_session(fake):
                pass
        assert fake.entered is True
        assert fake.exited is True

    async def test_finalize_failure_still_exits_underlying_session(self, monkeypatch):
        fake = FakeSession([])
        monkeypatch.setattr(
            EventSession, "finalize", mock.Mock(side_effect=RuntimeError("boom"))
        )
        # __aexit__ must swallow the finalize error and still exit the session.
        async with wrap_realtime_session(fake) as conn:
            assert conn is not None
        assert fake.exited is True

    async def test_max_audio_seconds_bounds_recording(self):
        async with wrap_realtime_session(
            FakeSession([]), sample_rate=10, max_audio_seconds=1.0
        ) as conn:
            # cap = 1.0s * 10 * 2 = 20 bytes per channel.
            conn.record_user_audio(b"\x00" * 16)  # kept
            conn.record_user_audio(b"\x00" * 16)  # kept (pushes over)
            conn.record_user_audio(b"\x00" * 16)  # dropped
            trace = conn._trace
        assert trace.max_audio_bytes == 20
        assert len(trace.user_chunks) == 2
        assert trace._audio_truncated is True
