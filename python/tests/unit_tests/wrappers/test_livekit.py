"""Unit tests for the LiveKit voice tracing integration.

Pure unit tests: the ``LiveKitLangSmithSpanProcessor`` imports only
``opentelemetry`` (+ the shared base), never ``livekit-agents``, so spans are
mocked and no framework install is needed.
"""

import base64
import json
import sys
import threading
import time
import warnings
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from langsmith._internal.voice import set_thread_id
from langsmith.integrations.livekit import configure_livekit
from langsmith.integrations.livekit._helpers import (
    build_assistant_tool_call_message,
    build_message_from_event,
    normalize_provider,
)
from langsmith.integrations.livekit.processor import (
    LiveKitLangSmithSpanProcessor,
)


def _make_span(
    name,
    attributes=None,
    *,
    trace_id=0xABC,
    span_id=0x1,
    parent=True,
    scope="livekit-agents",
    start_time=None,
):
    """Build a mock LiveKit span.

    The processor only reads ``span.attributes`` (and read-only fields); it never
    mutates the span — translation accumulates on a ``TranslatedSpan`` draft and a
    fresh span is built for export, so assertions read the exported span's
    ``_attributes`` (see the call sites). ``parent=None`` marks the trace root
    (LiveKit's job entrypoint); otherwise a non-None parent is supplied. ``scope``
    is the instrumentation-scope name; it defaults to LiveKit's so spans are
    recognized — pass another value to simulate a non-LiveKit run on the same
    provider.
    """
    span = MagicMock()
    span.name = name
    span.attributes = dict(attributes or {})
    span.events = []
    span.context = MagicMock()
    span.context.trace_id = trace_id
    span.context.span_id = span_id
    # start_time (ns) is the root's conversation-ordering key; default to span_id
    # so spans sort in a stable, explicit order without every test setting it.
    span.start_time = span_id if start_time is None else start_time
    span.parent = MagicMock() if parent else None
    span.instrumentation_scope = MagicMock()
    span.instrumentation_scope.name = scope
    return span


def _processor(**kwargs):
    return LiveKitLangSmithSpanProcessor(downstream_processor=MagicMock(), **kwargs)


def _start_span(proc, span, thread_id):
    set_thread_id(thread_id)
    proc.on_start(span)
    set_thread_id(None)
    return span


class TestDeprecatedAudioPathProvider:
    def test_is_accepted_but_not_called(self):
        provider = MagicMock()

        with pytest.warns(
            DeprecationWarning, match="audio_path_provider is deprecated and ignored"
        ):
            _processor(audio_path_provider=provider)

        provider.assert_not_called()

    def test_none_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            _processor(audio_path_provider=None)


class TestDispatchDisposition:
    """``_dispatch`` decides whether the base exports each span."""

    def test_normal_span_exported(self):
        proc = _processor()
        span = _make_span("user_turn", {"lk.user_transcript": "hi"})
        proc.on_end(span)
        proc.downstream.on_end.assert_called_once()

    def test_realtime_metrics_exported_as_llm(self):
        # An orphaned realtime_metrics span carries the model usage → llm run.
        proc = _processor()
        span = _make_span("realtime_metrics", {"lk.realtime_model_metrics": "{}"})
        proc.on_end(span)
        exported = proc.downstream.on_end.call_args.args[0]
        assert exported._attributes["langsmith.span.kind"] == "llm"

    def test_root_deferred_not_exported_immediately(self):
        proc = _processor()
        root = _make_span("job_entrypoint", parent=None)
        proc.on_end(root)
        # Held open until the session ends — not exported yet.
        proc.downstream.on_end.assert_not_called()

    def test_non_livekit_root_exported_untouched(self):
        # A parentless span from another instrumentation (e.g. a LangChain root
        # riding the same OTel provider) must NOT be hijacked as the LiveKit
        # conversation root — it is exported as-is, not deferred or relabeled.
        proc = _processor()
        span = _make_span("ChatOpenAI", parent=None, scope="langsmith")
        proc.on_end(span)
        exported = proc.downstream.on_end.call_args.args[0]
        assert "langsmith.root_span" not in exported._attributes
        assert "langsmith.metadata.ls_modality" not in exported._attributes
        assert len(proc._state_by_trace) == 0

    def test_non_livekit_trace_cannot_hijack_recording_route(self):
        proc = _processor()
        set_thread_id("call-1")
        proc.on_start(_make_span("job_entrypoint", parent=None, trace_id=0xABC))
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=0xABC))

        proc.on_start(
            _make_span(
                "ChatOpenAI",
                parent=None,
                scope="langsmith",
                trace_id=0xDEF,
            )
        )
        set_thread_id(None)

        assert proc._trace_by_thread["call-1"] == 0xABC

    def test_egress_root_without_thread_warns_once(self, caplog):
        proc = _processor(recording_mode="egress")
        proc.on_end(_make_span("job_entrypoint", parent=None))
        proc.on_end(_make_span("agent_session", span_id=0x2))

        warnings = [
            message for message in caplog.messages if "has no thread id" in message
        ]
        assert len(warnings) == 1


class TestDeferredRootRelease:
    """The root is held until ``agent_session`` ends, then rendered + exported."""

    def test_session_end_releases_root_with_transcript(self):
        proc = _processor()
        tid = 0xABC
        # Root ends first (agent greets), then a turn, then the session ends.
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=tid))
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.user_input": "weather?", "lk.response.text": "sunny"},
                trace_id=tid,
                span_id=0x2,
            )
        )
        # The turn span exports normally; only the root is held back.
        assert not any(
            c.args[0]._attributes.get("langsmith.root_span")
            for c in proc.downstream.on_end.call_args_list
        )

        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))

        # Session span + released root both exported.
        exported = [c.args[0] for c in proc.downstream.on_end.call_args_list]
        root = next(s for s in exported if s._attributes.get("langsmith.root_span"))
        assert root._attributes["langsmith.metadata.ls_modality"] == "audio"
        # The root is attributed to this integration so usage is trackable.
        assert root._attributes["langsmith.metadata.ls_integration"] == "livekit"
        # The whole transcript lands on the root's input.
        prompt = json.loads(root._attributes["gen_ai.prompt"])["messages"]
        assert [m["content"] for m in prompt] == ["weather?", "sunny"]
        assert "gen_ai.completion" not in root._attributes
        # Per-conversation state freed after release.
        assert len(proc._state_by_trace) == 0


class TestRealtimeUserTranscript:
    """Realtime (speech-to-speech) user transcripts fed via instrument_session.

    In the realtime pipeline there is no STT ``user_turn`` span; LiveKit emits a
    bare ``user_speaking`` span and delivers the transcript out of band via the
    ``user_input_transcribed`` event. The host forwards it to the processor, which
    holds the span until the transcript arrives, then stamps it on.
    """

    def teardown_method(self):
        set_thread_id(None)

    def _speaking(self, *, trace_id=0xABC, span_id=0x2):
        return _make_span(
            "user_speaking",
            trace_id=trace_id,
            span_id=span_id,
        )

    def _exported(self, proc, name):
        return [
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0].name == name
        ]

    def test_transcript_after_span_stamps_and_exports(self):
        # Span ends empty first (held), then the transcript arrives.
        proc = _processor()
        proc.on_end(_start_span(proc, self._speaking(), "call-1"))
        # Held — nothing exported yet.
        assert self._exported(proc, "user_speaking") == []

        proc._record_user_transcript("call-1", "what's the weather?")

        exported = self._exported(proc, "user_speaking")
        assert len(exported) == 1
        span = exported[0]
        assert span._attributes["lk.user_transcript"] == "what's the weather?"
        assert span._attributes["langsmith.span.kind"] == "llm"
        # Rendered as the user's turn (not excluded, not attributed to assistant).
        assert "langsmith.metadata.ls_message_view_exclude" not in span._attributes
        assert json.loads(span._attributes["gen_ai.prompt"])["messages"][0] == {
            "role": "user",
            "content": "what's the weather?",
        }
        assert "gen_ai.completion" not in span._attributes
        # No state left behind.
        state = proc._state_by_trace[0xABC]
        assert state.spans_waiting_for_transcript == []
        assert state.transcripts_waiting_for_span == []

    def test_transcript_before_span_is_buffered(self):
        # Transcript can race ahead of the span's on_end — buffer, then apply.
        proc = _processor()
        proc._record_user_transcript("call-1", "hello there")
        assert self._exported(proc, "user_speaking") == []

        proc.on_end(_start_span(proc, self._speaking(), "call-1"))

        exported = self._exported(proc, "user_speaking")
        assert len(exported) == 1
        assert exported[0]._attributes["lk.user_transcript"] == "hello there"
        assert len(proc._transcripts_waiting_for_trace) == 0

    def test_fifo_pairing_within_conversation(self):
        # Two utterances, two transcripts — paired in order.
        proc = _processor()
        proc.on_end(_start_span(proc, self._speaking(span_id=0x2), "call-1"))
        proc.on_end(_start_span(proc, self._speaking(span_id=0x3), "call-1"))
        proc._record_user_transcript("call-1", "first")
        proc._record_user_transcript("call-1", "second")

        transcripts = [
            s._attributes["lk.user_transcript"]
            for s in self._exported(proc, "user_speaking")
        ]
        assert transcripts == ["first", "second"]

    def test_no_thread_id_exports_untouched(self):
        # Without a thread id there is nothing to pair against — export as-is.
        proc = _processor()
        proc.on_end(_make_span("user_speaking", trace_id=0xABC, span_id=0x2))
        exported = self._exported(proc, "user_speaking")
        assert len(exported) == 1
        assert exported[0]._attributes["langsmith.span.kind"] == "chain"
        assert "lk.user_transcript" not in exported[0]._attributes

    def test_empty_transcript_consumes_slot_without_fake_io(self):
        # A final-but-empty transcript still pairs (keeping FIFO aligned) but
        # renders no fabricated I/O.
        proc = _processor()
        proc.on_end(_start_span(proc, self._speaking(), "call-1"))
        proc._record_user_transcript("call-1", "")

        exported = self._exported(proc, "user_speaking")
        assert len(exported) == 1
        assert "gen_ai.completion" not in exported[0]._attributes
        assert "lk.user_transcript" not in exported[0]._attributes

    def test_session_end_flushes_untranscribed_span(self):
        # Realtime input transcription disabled: no transcript ever arrives, so
        # the held span must still be exported (untouched) at session end.
        proc = _processor()
        tid = 0xABC
        # Production flow: set_thread_id + on_start caches the trace's thread id,
        # so the session-end flush can resolve which held spans to release.
        set_thread_id("call-1")
        proc.on_start(_make_span("job_entrypoint", parent=None, trace_id=tid))
        set_thread_id(None)
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=tid))
        proc.on_end(_start_span(proc, self._speaking(trace_id=tid), "call-1"))
        assert self._exported(proc, "user_speaking") == []  # held

        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))

        assert len(self._exported(proc, "user_speaking")) == 1
        assert proc._state_by_trace[tid].spans_waiting_for_transcript == []

    def test_shutdown_flushes_untranscribed_span(self):
        proc = _processor(recording_mode="none")
        proc.on_end(_start_span(proc, self._speaking(), "call-1"))
        proc.shutdown()
        assert len(self._exported(proc, "user_speaking")) == 1


class TestRealtimeRootRollup:
    """A late realtime user transcript sorts into its place in the root rollup.

    The transcript arrives after its turn's ``agent_turn`` reply is already
    recorded, so ordering keys off each message's source-span start_time — the
    ``user_speaking`` span (earlier) before the ``agent_turn`` reply (later).
    """

    def _root(self, proc):
        return next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0]._attributes.get("langsmith.root_span")
        )

    def test_user_sorts_before_reply_despite_late_arrival(self):
        proc = _processor(recording_mode="none")
        tid = 0xABC
        proc.on_end(
            _start_span(
                proc,
                _make_span(
                    "job_entrypoint",
                    parent=None,
                    trace_id=tid,
                ),
                "call-1",
            )
        )
        # User speaks (early span), then the reply turn lands and is recorded...
        proc.on_end(
            _make_span(
                "user_speaking",
                trace_id=tid,
                span_id=0x2,
                start_time=10,
            )
        )
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.response.text": "sunny"},
                trace_id=tid,
                span_id=0x3,
                start_time=20,
            )
        )
        # ...only *then* does the transcript arrive (out of order).
        proc._record_user_transcript("call-1", "weather?")
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x4))
        proc.attach_session_report(_report(), thread_id="call-1")

        root = self._root(proc)
        prompt = json.loads(root._attributes["gen_ai.prompt"])["messages"]
        assert [m["content"] for m in prompt] == ["weather?", "sunny"]
        assert "gen_ai.completion" not in root._attributes

    def test_greeting_then_user_turn_ordered(self):
        # Agent greets first (agent_turn, no user_speaking), then a user turn.
        # The greeting must not steal the user's transcript, and order holds.
        proc = _processor(recording_mode="none")
        tid = 0xABC
        proc.on_end(
            _start_span(
                proc,
                _make_span(
                    "job_entrypoint",
                    parent=None,
                    trace_id=tid,
                ),
                "call-1",
            )
        )
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.response.text": "hi there!"},
                trace_id=tid,
                span_id=0x2,
                start_time=5,
            )
        )
        proc.on_end(
            _make_span(
                "user_speaking",
                trace_id=tid,
                span_id=0x3,
                start_time=10,
            )
        )
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.response.text": "sunny"},
                trace_id=tid,
                span_id=0x4,
                start_time=20,
            )
        )
        proc._record_user_transcript("call-1", "weather?")
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x5))
        proc.attach_session_report(_report(), thread_id="call-1")

        root = self._root(proc)
        contents = [
            m["content"]
            for m in json.loads(root._attributes["gen_ai.prompt"])["messages"]
        ]
        assert contents == ["hi there!", "weather?", "sunny"]


class TestInstrumentSession:
    """instrument_session subscribes the processor to a session's events itself."""

    class _FakeSession:
        """Minimal stand-in for a LiveKit AgentSession's event emitter."""

        def __init__(self):
            self.handlers = {}

        def on(self, name):
            def _register(fn):
                self.handlers[name] = fn
                return fn

            return _register

    @staticmethod
    def _event(*, is_final, transcript):
        ev = MagicMock()
        ev.is_final = is_final
        ev.transcript = transcript
        return ev

    def test_final_transcript_wired_to_processor(self):
        proc = _processor()
        session = self._FakeSession()
        proc.instrument_session(session, "call-1")

        span = _make_span("user_speaking", span_id=0x2)
        proc.on_end(_start_span(proc, span, "call-1"))
        session.handlers["user_input_transcribed"](
            self._event(is_final=True, transcript="hello there")
        )

        exported = [
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0].name == "user_speaking"
        ]
        assert len(exported) == 1
        assert exported[0]._attributes["lk.user_transcript"] == "hello there"

    def test_interim_transcript_ignored(self):
        proc = _processor()
        session = self._FakeSession()
        proc.instrument_session(session, "call-1")

        session.handlers["user_input_transcribed"](
            self._event(is_final=False, transcript="partial")
        )
        # Interim result buffered nothing; a later span has no transcript to pair.
        assert len(proc._transcripts_waiting_for_trace) == 0


class TestForceFlush:
    """force_flush must not finalize conversations still in progress."""

    def test_force_flush_keeps_in_progress_root(self):
        # Root has ended (agent greeted) but the session has NOT — the root is
        # legitimately deferred. A mid-conversation force_flush must leave it held
        # and not emit a partial root, so the real one survives to session end.
        proc = _processor()
        tid = 0xABC
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=tid))
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.user_input": "weather?", "lk.response.text": "sunny"},
                trace_id=tid,
                span_id=0x2,
            )
        )

        proc.force_flush()

        # No root emitted, and it is still held for the (not-yet-ended) session.
        assert not any(
            c.args[0]._attributes.get("langsmith.root_span")
            for c in proc.downstream.on_end.call_args_list
        )
        assert proc._state_by_trace[tid].root is not None

        # When the session finally ends, the complete root is exported once.
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))
        root = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0]._attributes.get("langsmith.root_span")
        )
        prompt = json.loads(root._attributes["gen_ai.prompt"])["messages"]
        assert prompt[-1]["content"] == "sunny"

    def test_shutdown_flushes_held_root(self):
        # shutdown IS terminal: a still-held root is flushed as a last resort.
        proc = _processor()
        tid = 0xABC
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=tid))
        proc.shutdown()
        assert any(
            c.args[0]._attributes.get("langsmith.root_span")
            for c in proc.downstream.on_end.call_args_list
        )


class _FakeChatHistory:
    """Stands in for LiveKit's ``ChatContext``; only ``to_dict`` is read.

    The keyword list mirrors the public ``livekit-agents>=1.3`` contract.
    """

    def __init__(self, items):
        self._items = items

    def to_dict(
        self,
        *,
        exclude_image=True,
        exclude_audio=True,
        exclude_timestamp=True,
        exclude_function_call=False,
        exclude_metrics=False,
        exclude_config_update=False,
    ):
        # The processor must ask for timestamps and keep function calls — the
        # transcript is ordered by created_at and shows the tool calls.
        assert exclude_timestamp is False
        assert exclude_function_call is False
        return {"items": self._items}


def _report(*, path=None, started_at=None, items=None):
    """A duck-typed LiveKit ``SessionReport``."""
    return SimpleNamespace(
        audio_recording_path=path,
        audio_recording_started_at=started_at,
        chat_history=_FakeChatHistory(items or []),
    )


class _FakeLifecycleSession:
    """Minimal additive/one-shot LiveKit session event emitter."""

    def __init__(self):
        self.listeners = {}

    def once(self, name, callback):
        self.listeners.setdefault(name, []).append(callback)

    def close(self):
        callbacks = self.listeners.pop("close", [])
        for callback in callbacks:
            callback(SimpleNamespace())


class _FakeJobContext:
    def __init__(self, session, report):
        self._primary_agent_session = session
        self.report = report
        self.make_report_calls = []

    def make_session_report(self, session):
        self.make_report_calls.append(session)
        return self.report


def _install_fake_livekit(monkeypatch, current_context, telemetry=None):
    """Install the tiny optional LiveKit surface the processor/configure use."""
    agents_module = ModuleType("livekit.agents")
    agents_module.get_job_context = lambda required=False: current_context["value"]
    agents_module.telemetry = telemetry or SimpleNamespace(
        set_tracer_provider=MagicMock()
    )
    livekit_module = ModuleType("livekit")
    livekit_module.agents = agents_module
    monkeypatch.setitem(sys.modules, "livekit", livekit_module)
    monkeypatch.setitem(sys.modules, "livekit.agents", agents_module)
    return agents_module


# One second in nanoseconds — root start times are OTel ns, origins are epoch s.
_NS = 1_000_000_000
_ROOT_START_NS = 1_700_000_000 * _NS


class _RecordingHarness:
    """Drives one conversation through the processor: start, spans, session end."""

    def teardown_method(self):
        set_thread_id(None)

    def _start_conversation(
        self, proc, tid=0xABC, start_time=_ROOT_START_NS, thread_id="call-1"
    ):
        # The root's thread id comes from set_thread_id (captured at on_start),
        # exactly as in production; clearing it after simulates the detached end.
        set_thread_id(thread_id)
        proc.on_start(
            _make_span(
                "job_entrypoint", parent=None, trace_id=tid, start_time=start_time
            )
        )
        set_thread_id(None)
        proc.on_end(
            _make_span(
                "job_entrypoint", parent=None, trace_id=tid, start_time=start_time
            )
        )

    def _end_session(self, proc, tid=0xABC):
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))

    def _start_session(self, proc, thread_id="call-1", tid=0xABC):
        set_thread_id(thread_id)
        proc.on_start(_make_span("agent_session", trace_id=tid, span_id=0x2))
        set_thread_id(None)

    def _root(self, proc):
        return next(
            (
                c.args[0]
                for c in proc.downstream.on_end.call_args_list
                if c.args[0]._attributes.get("langsmith.root_span")
            ),
            None,
        )


class TestAutomaticSessionReport(_RecordingHarness):
    def test_report_hook_correlates_unthreaded_trace_by_trace_id(
        self, monkeypatch, tmp_path
    ):
        audio = tmp_path / "unthreaded.ogg"
        audio.write_bytes(b"unthreaded-audio")
        session = _FakeLifecycleSession()
        ctx = _FakeJobContext(session, _report(path=audio))
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor()

        self._start_conversation(proc, thread_id=None)
        self._start_session(proc, thread_id=None)
        self._end_session(proc)
        assert self._root(proc) is None

        session.close()

        root = self._root(proc)
        payload = json.loads(root._attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"unthreaded-audio"
        assert "langsmith.metadata.thread_id" not in root._attributes
        assert ctx.make_report_calls == [session]

    def test_unthreaded_egress_does_not_wait_for_report(self, monkeypatch):
        session = _FakeLifecycleSession()
        ctx = _FakeJobContext(session, _report())
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor(recording_mode="egress")

        self._start_conversation(proc, thread_id=None)
        self._start_session(proc, thread_id=None)
        self._end_session(proc)

        assert self._root(proc) is not None

    def test_direct_processor_captures_report_on_session_close(
        self, monkeypatch, tmp_path
    ):
        audio = tmp_path / "automatic.ogg"
        audio.write_bytes(b"automatic-audio")
        session = _FakeLifecycleSession()
        ctx = _FakeJobContext(session, _report(path=audio, items=[]))
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor()

        self._start_conversation(proc)
        self._start_session(proc)
        self._end_session(proc)
        assert self._root(proc) is None

        session.close()

        root = self._root(proc)
        payload = json.loads(root._attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"automatic-audio"
        assert ctx.make_report_calls == [session]

    def test_configured_processor_installs_the_same_automatic_hook(self, monkeypatch):
        from opentelemetry import trace as otel_trace

        session = _FakeLifecycleSession()
        ctx = _FakeJobContext(session, _report())
        current_context = {"value": ctx}
        telemetry = SimpleNamespace(set_tracer_provider=MagicMock())
        _install_fake_livekit(monkeypatch, current_context, telemetry=telemetry)
        monkeypatch.setattr(otel_trace, "set_tracer_provider", MagicMock())

        proc = configure_livekit(downstream_processor=MagicMock())
        assert proc is not None
        self._start_conversation(proc)
        self._start_session(proc)
        self._end_session(proc)
        session.close()

        assert self._root(proc) is not None
        telemetry.set_tracer_provider.assert_called_once()

    def test_existing_close_listener_is_preserved(self, monkeypatch):
        session = _FakeLifecycleSession()
        existing = MagicMock()
        session.once("close", existing)
        ctx = _FakeJobContext(session, _report())
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor(recording_mode="none")

        self._start_conversation(proc)
        self._start_session(proc)
        self._end_session(proc)
        session.close()

        existing.assert_called_once()
        assert self._root(proc) is not None

    def test_egress_waits_for_automatic_report_and_completion(self, monkeypatch):
        session = _FakeLifecycleSession()
        report = _report()
        ctx = _FakeJobContext(session, report)
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor(recording_mode="egress")

        self._start_conversation(proc)
        self._start_session(proc)
        self._end_session(proc)
        session.close()
        assert self._root(proc) is None

        # A duplicate manual delivery is harmless while the egress root is held.
        proc.attach_session_report(report, thread_id="call-1")
        proc.complete_recording("call-1", b"egress")

        roots = [
            call.args[0]
            for call in proc.downstream.on_end.call_args_list
            if call.args[0]._attributes.get("langsmith.root_span")
        ]
        assert len(roots) == 1
        assert "langsmith.attachments" in roots[0]._attributes

    def test_hook_registration_is_idempotent(self, monkeypatch):
        session = _FakeLifecycleSession()
        ctx = _FakeJobContext(session, _report())
        current_context = {"value": ctx}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor()

        self._start_conversation(proc)
        self._start_session(proc)
        self._start_session(proc)

        assert len(session.listeners["close"]) == 1
        self._end_session(proc)
        session.close()
        assert ctx.make_report_calls == [session]
        assert self._root(proc) is not None

    def test_reports_route_to_the_captured_trace(self, monkeypatch):
        session_a = _FakeLifecycleSession()
        session_b = _FakeLifecycleSession()
        ctx_a = _FakeJobContext(
            session_a,
            _report(
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["A"],
                        "created_at": 1,
                    }
                ]
            ),
        )
        ctx_b = _FakeJobContext(
            session_b,
            _report(
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["B"],
                        "created_at": 1,
                    }
                ]
            ),
        )
        current_context = {"value": ctx_a}
        _install_fake_livekit(monkeypatch, current_context)
        proc = _processor(recording_mode="none")

        self._start_conversation(proc, tid=0xAAA, thread_id="thread-a")
        self._start_session(proc, tid=0xAAA, thread_id="thread-a")
        current_context["value"] = ctx_b
        self._start_conversation(proc, tid=0xBBB, thread_id="thread-b")
        self._start_session(proc, tid=0xBBB, thread_id="thread-b")
        self._end_session(proc, tid=0xAAA)
        self._end_session(proc, tid=0xBBB)

        session_b.close()
        session_a.close()

        roots = {
            call.args[0].context.trace_id: call.args[0]
            for call in proc.downstream.on_end.call_args_list
            if call.args[0]._attributes.get("langsmith.root_span")
        }
        prompt_a = json.loads(roots[0xAAA]._attributes["gen_ai.prompt"])
        prompt_b = json.loads(roots[0xBBB]._attributes["gen_ai.prompt"])
        assert prompt_a["messages"][0]["content"] == "A"
        assert prompt_b["messages"][0]["content"] == "B"


class TestEgressRecording(_RecordingHarness):
    """Egress report data and external audio may arrive in either order."""

    def test_report_then_recording(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        assert self._root(proc) is None

        proc.complete_recording("call-1", data=b"OggS-bytes", name="call.ogg")

        root = self._root(proc)
        payload = json.loads(root._attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"OggS-bytes"
        assert payload[0]["name"] == "call.ogg"
        assert payload[0]["mime_type"] == "audio/ogg"
        assert (
            root._attributes["langsmith.metadata.ls_audio_attach_status"] == "attached"
        )

    def test_recording_then_report(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.complete_recording("call-1", b"OggS-bytes")
        assert self._root(proc) is None

        proc.attach_session_report(_report(), thread_id="call-1")

        assert "langsmith.attachments" in self._root(proc)._attributes

    def test_report_audio_is_ignored(self, tmp_path):
        report_audio = tmp_path / "report.ogg"
        report_audio.write_bytes(b"wrong audio")
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)

        proc.attach_session_report(_report(path=report_audio), thread_id="call-1")
        proc.complete_recording("call-1", b"egress audio")

        payload = json.loads(self._root(proc)._attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"egress audio"

    def test_terminal_recording_failure_releases_without_audio(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        assert self._root(proc) is None

        proc.complete_recording("call-1", None)

        root = self._root(proc)
        assert "langsmith.attachments" not in root._attributes
        assert root._attributes["langsmith.metadata.ls_audio_attach_status"] == "none"

    def test_started_at_stamps_the_offset(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        proc.complete_recording(
            "call-1",
            b"x",
            started_at=(_ROOT_START_NS / 1e9) + 4.25,
        )

        md = self._root(proc)._attributes
        assert md["langsmith.metadata.ls_audio_recording_start_offset_ms"] == 4250

    def test_complete_recording_before_spans_selects_egress_for_that_thread(self):
        proc = _processor()
        proc.complete_recording("call-1", b"x")
        self._start_conversation(proc)
        state = proc._get_state_by_thread("call-1")
        assert state.recording_mode == "egress"
        assert state.recording_received is True
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        assert "langsmith.attachments" in self._root(proc)._attributes

    def test_expect_recording_before_spans_overrides_only_that_thread(self):
        proc = _processor()
        proc.expect_recording("call-1")
        self._start_conversation(proc)

        state = proc._get_state_by_thread("call-1")
        assert state.recording_mode == "egress"
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        assert self._root(proc) is None

        proc.complete_recording("call-1", b"x")
        assert "langsmith.attachments" in self._root(proc)._attributes

    def test_expect_recording_can_override_after_spans_arrive(self):
        proc = _processor()
        self._start_conversation(proc)
        proc.expect_recording("call-1")

        assert proc._get_state_by_thread("call-1").recording_mode == "egress"

    def test_expect_recording_does_not_change_other_conversations(self):
        proc = _processor()
        proc.expect_recording("egress-call")
        self._start_conversation(proc, tid=0xAAA, thread_id="egress-call")
        self._start_conversation(proc, tid=0xBBB, thread_id="report-call")
        self._end_session(proc, tid=0xAAA)
        self._end_session(proc, tid=0xBBB)

        proc.attach_session_report(_report(), thread_id="egress-call")
        proc.attach_session_report(_report(), thread_id="report-call")
        exported_trace_ids = {
            call.args[0].context.trace_id
            for call in proc.downstream.on_end.call_args_list
            if call.args[0]._attributes.get("langsmith.root_span")
        }
        assert exported_trace_ids == {0xBBB}

        proc.complete_recording("egress-call", b"x")
        exported_trace_ids = {
            call.args[0].context.trace_id
            for call in proc.downstream.on_end.call_args_list
            if call.args[0]._attributes.get("langsmith.root_span")
        }
        assert exported_trace_ids == {0xAAA, 0xBBB}

    def test_processor_egress_default_does_not_require_expect_recording(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        assert self._root(proc) is None

        proc.complete_recording("call-1", b"x")
        assert self._root(proc) is not None

    def test_late_recording_is_not_reused_by_a_future_trace(self, caplog):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")
        proc.complete_recording("call-1", b"first")

        proc.complete_recording("call-1", b"late")

        assert "call-1" not in proc._thread_state_waiting_for_trace
        assert any("no active LiveKit trace" in message for message in caplog.messages)

    def test_oversize_recording_is_not_buffered(self):
        proc = _processor(recording_mode="egress", audio_size_limit_bytes=3)
        self._start_conversation(proc)
        proc.complete_recording("call-1", b"large")

        state = proc._get_state_by_thread("call-1")
        assert state.recording_received is True
        assert state.pending_audio is None
        assert state.audio_status == "too_large"


class TestSessionReport(_RecordingHarness):
    """attach_session_report delivers audio, origin, and transcript in one call."""

    def test_attaches_audio_and_offset(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"OggS-session")
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        assert self._root(proc) is None

        proc.attach_session_report(
            _report(path=audio, started_at=(_ROOT_START_NS / 1e9) + 2.8),
            thread_id="call-1",
        )

        root = self._root(proc)
        md = root._attributes
        payload = json.loads(md["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"OggS-session"
        assert payload[0]["name"] == "audio.ogg"
        assert md["langsmith.metadata.ls_audio_recording_start_offset_ms"] == 2800
        assert md["langsmith.metadata.ls_audio_recording_started_at"] == pytest.approx(
            (_ROOT_START_NS / 1e9) + 2.8
        )
        assert md["langsmith.metadata.ls_audio_attach_status"] == "attached"

    def test_offset_can_be_negative(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"x")
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        # A recording that predates the trace must not be clamped to zero.
        proc.attach_session_report(
            _report(path=audio, started_at=(_ROOT_START_NS / 1e9) - 1.5),
            thread_id="call-1",
        )

        offset = self._root(proc)._attributes[
            "langsmith.metadata.ls_audio_recording_start_offset_ms"
        ]
        assert offset == -1500

    def test_absent_origin_stamps_neither_key(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"x")
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(
            _report(path=audio, started_at=None), thread_id="call-1"
        )

        md = self._root(proc)._attributes
        assert "langsmith.metadata.ls_audio_recording_started_at" not in md
        assert "langsmith.metadata.ls_audio_recording_start_offset_ms" not in md
        # The audio still attaches; only the alignment is unknown.
        assert "langsmith.attachments" in md

    def test_oversize_recording_is_never_read(self, tmp_path):
        audio = tmp_path / "audio.ogg"
        audio.write_bytes(b"x" * 500)
        proc = _processor(audio_size_limit_bytes=100)
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(path=audio), thread_id="call-1")

        md = self._root(proc)._attributes
        assert "langsmith.attachments" not in md
        assert md["langsmith.metadata.ls_audio_attach_status"] == "too_large"

    def test_missing_file_reports_unreadable(self, tmp_path):
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(
            _report(path=tmp_path / "gone.ogg"), thread_id="call-1"
        )

        md = self._root(proc)._attributes
        assert "langsmith.attachments" not in md
        assert md["langsmith.metadata.ls_audio_attach_status"] == "unreadable"

    def test_empty_file_reports_none(self, tmp_path):
        audio = tmp_path / "empty.ogg"
        audio.write_bytes(b"")
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(path=audio), thread_id="call-1")

        md = self._root(proc)._attributes
        assert "langsmith.attachments" not in md
        assert md["langsmith.metadata.ls_audio_attach_status"] == "none"


class TestEgressDeliveryRace(_RecordingHarness):
    """The report/recording race exports exactly one complete root."""

    def test_concurrent_report_and_recording_export_once(self):
        for attempt in range(40):
            proc = _processor(recording_mode="egress", recording_timeout_seconds=5.0)
            self._start_conversation(proc, tid=0xABC + attempt)
            self._end_session(proc, tid=0xABC + attempt)

            report = _report(
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["Hello"],
                        "created_at": 1.0,
                    }
                ]
            )
            start = threading.Barrier(2)

            def deliver_report():
                start.wait()
                proc.attach_session_report(report, thread_id="call-1")

            def deliver_recording():
                start.wait()
                proc.complete_recording("call-1", b"OggS-egress", started_at=1.0)

            threads = [
                threading.Thread(target=deliver_report),
                threading.Thread(target=deliver_recording),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            roots = [
                c.args[0]
                for c in proc.downstream.on_end.call_args_list
                if c.args[0]._attributes.get("langsmith.root_span")
            ]
            assert len(roots) == 1, f"attempt {attempt}: {len(roots)} roots"
            assert "langsmith.attachments" in roots[0]._attributes, attempt
            messages = json.loads(roots[0]._attributes["gen_ai.prompt"])["messages"]
            assert messages == [{"role": "user", "content": "Hello"}]


class TestRecordingTimeout(_RecordingHarness):
    """A recording that never arrives yields a trace without audio, not no trace."""

    def test_shutdown_waits_for_in_flight_timeout_export(self):
        proc = _processor(recording_timeout_seconds=60.0)
        self._start_conversation(proc)
        self._end_session(proc)
        state = proc._get_state_by_thread("call-1")
        assert state is not None
        assert state.release_timer is not None
        state.release_timer.cancel()

        export_started = threading.Event()
        allow_export = threading.Event()
        shutdown_started = threading.Event()
        shutdown_finished = threading.Event()
        original_export = proc._export_completed_conversation

        def blocking_export(state, root):
            export_started.set()
            assert allow_export.wait(timeout=5)
            original_export(state, root)

        def shut_down():
            shutdown_started.set()
            proc.shutdown()
            shutdown_finished.set()

        proc._export_completed_conversation = blocking_export
        timeout_thread = threading.Thread(
            target=proc._on_recording_timeout, args=(0xABC,)
        )
        timeout_thread.start()
        assert export_started.wait(timeout=5)

        shutdown_thread = threading.Thread(target=shut_down)
        shutdown_thread.start()
        assert shutdown_started.wait(timeout=5)
        assert not shutdown_finished.wait(timeout=0.05)

        allow_export.set()
        timeout_thread.join(timeout=5)
        shutdown_thread.join(timeout=5)

        assert not timeout_thread.is_alive()
        assert not shutdown_thread.is_alive()
        assert shutdown_finished.is_set()
        assert self._root(proc) is not None
        proc.downstream.shutdown.assert_called_once()

    def test_timeout_releases_the_root(self):
        proc = _processor(recording_timeout_seconds=0.05)
        self._start_conversation(proc)
        self._end_session(proc)
        assert self._root(proc) is None

        deadline = time.monotonic() + 2.0
        while self._root(proc) is None and time.monotonic() < deadline:
            time.sleep(0.01)

        root = self._root(proc)
        assert root is not None
        assert "langsmith.attachments" not in root._attributes
        assert (
            root._attributes["langsmith.metadata.ls_audio_attach_status"] == "timeout"
        )

    def test_egress_timeout_releases_when_recording_never_arrives(self):
        proc = _processor(recording_mode="egress", recording_timeout_seconds=0.05)
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(_report(), thread_id="call-1")

        deadline = time.monotonic() + 2.0
        while self._root(proc) is None and time.monotonic() < deadline:
            time.sleep(0.01)

        root = self._root(proc)
        assert root is not None
        assert (
            root._attributes["langsmith.metadata.ls_audio_attach_status"] == "timeout"
        )

    def test_none_mode_waits_for_report(self):
        proc = _processor(recording_mode="none")
        self._start_conversation(proc)
        self._end_session(proc)
        assert self._root(proc) is None

        proc.attach_session_report(_report(), thread_id="call-1")

        assert self._root(proc) is not None

    @pytest.mark.parametrize("timeout", [0, -1])
    def test_nonpositive_timeout_is_rejected(self, timeout):
        with pytest.raises(ValueError, match="greater than zero"):
            _processor(recording_timeout_seconds=timeout)

    def test_unknown_recording_mode_is_rejected(self):
        with pytest.raises(ValueError, match="recording_mode"):
            _processor(recording_mode="automatic")


class TestChatHistoryTranscript(_RecordingHarness):
    """The root transcript comes from the report's chat history when present."""

    def _messages(self, root):
        return json.loads(root._attributes["gen_ai.prompt"])["messages"]

    def _audio(self, tmp_path):
        """A recording on the report, so it releases the root on arrival."""
        f = tmp_path / "audio.ogg"
        f.write_bytes(b"OggS")
        return f

    def test_preserves_livekit_item_order_and_keeps_instructions(self, tmp_path):
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(
            _report(
                path=self._audio(tmp_path),
                items=[
                    {
                        "type": "message",
                        "role": "system",
                        "content": ["You are a bot"],
                        "created_at": 20.0,
                    },
                    {
                        "type": "message",
                        "role": "developer",
                        "content": ["Be concise"],
                        "created_at": 0.0,
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["Hello"],
                        "created_at": 10.0,
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": ["Hi there"],
                        "created_at": 5.0,
                    },
                ],
            ),
            thread_id="call-1",
        )

        messages = self._messages(self._root(proc))
        assert messages == [
            {"role": "system", "content": "You are a bot"},
            {"role": "developer", "content": "Be concise"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

    def test_keeps_function_calls_and_outputs(self, tmp_path):
        proc = _processor()
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(
            _report(
                path=self._audio(tmp_path),
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["Weather in Paris?"],
                        "created_at": 1.0,
                    },
                    {
                        "type": "function_call",
                        "call_id": "c1",
                        "name": "get_weather",
                        "arguments": '{"city": "Paris"}',
                        "created_at": 3.0,
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "c1",
                        "name": "get_weather",
                        "output": "18C",
                        "is_error": False,
                        "created_at": 4.0,
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": ["It's 18 degrees."],
                        "created_at": 2.0,
                    },
                ],
            ),
            thread_id="call-1",
        )

        messages = self._messages(self._root(proc))
        assert [m["role"] for m in messages] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]
        call = messages[1]["tool_calls"][0]
        assert call["id"] == "c1"
        assert call["function"]["name"] == "get_weather"
        assert json.loads(call["function"]["arguments"]) == {"city": "Paris"}
        assert messages[2] == {
            "role": "tool",
            "content": "18C",
            "tool_call_id": "c1",
            "name": "get_weather",
        }

    def test_egress_report_and_audio_are_combined(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        self._end_session(proc)

        proc.attach_session_report(
            _report(
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["Hello"],
                        "created_at": 1.0,
                    }
                ]
            ),
            thread_id="call-1",
        )
        proc.complete_recording(
            "call-1",
            b"OggS-egress",
            started_at=(_ROOT_START_NS / 1e9) + 3.0,
        )

        root = self._root(proc)
        md = root._attributes
        payload = json.loads(md["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"OggS-egress"
        assert md["langsmith.metadata.ls_audio_recording_start_offset_ms"] == 3000
        assert self._messages(root) == [{"role": "user", "content": "Hello"}]

    def test_none_mode_uses_report_transcript(self):
        proc = _processor(recording_mode="none")
        self._start_conversation(proc)
        self._end_session(proc)
        proc.attach_session_report(
            _report(
                items=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": ["Hello"],
                        "created_at": 1.0,
                    }
                ]
            ),
            thread_id="call-1",
        )
        root = self._root(proc)
        assert self._messages(root) == [{"role": "user", "content": "Hello"}]

    def test_egress_path_falls_back_to_span_rollup(self):
        proc = _processor(recording_mode="egress")
        self._start_conversation(proc)
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.user_input": "Hello", "lk.response.text": "Hi there"},
                trace_id=0xABC,
                span_id=0x2,
            )
        )
        self._end_session(proc)
        # An empty report transcript falls back to the conversation's spans.
        proc.attach_session_report(_report(), thread_id="call-1")
        proc.complete_recording("call-1", b"x")

        messages = self._messages(self._root(proc))
        assert [m["content"] for m in messages] == ["Hello", "Hi there"]


class TestStateTTL:
    """Per-conversation state is TTL-bounded so abandoned calls cannot leak."""

    def test_abandoned_state_expires(self):
        # A conversation whose session never ends must not leak; a zero TTL
        # drops it on the next write to that cache.
        proc = _processor(state_ttl_seconds=0)
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=0xAAA))
        # A later, different conversation's root triggers eviction of the first.
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=0xBBB))
        assert 0xAAA not in proc._state_by_trace

    def test_active_call_refreshes_transcript_ttl(self):
        proc = _processor(state_ttl_seconds=60)
        tid = 0xABC
        proc.on_end(
            _make_span(
                "agent_turn", {"lk.user_input": "one"}, trace_id=tid, span_id=0x2
            )
        )
        proc.on_end(
            _make_span(
                "agent_turn", {"lk.response.text": "two"}, trace_id=tid, span_id=0x3
            )
        )
        # One state object owns the ordered transcript.
        assert [m["content"] for _, m in proc._state_by_trace[tid].transcript] == [
            "one",
            "two",
        ]


class TestThreadId:
    """Thread id is injected from the per-context ``set_thread_id``."""

    def teardown_method(self):
        set_thread_id(None)

    def test_state_uses_captured_thread_id(self):
        proc = _processor()
        proc._remember_thread_id(0xABC, "call-1")

        with proc._state_lock:
            state = proc._get_or_create_state(0xABC)

        assert state.thread_id == "call-1"
        assert proc._trace_by_thread == {"call-1": 0xABC}

    def test_thread_cannot_route_to_two_active_traces(self):
        proc = _processor()
        proc._remember_thread_id(0xABC, "call-1")
        proc._remember_thread_id(0xDEF, "call-1")

        with proc._state_lock:
            first = proc._get_or_create_state(0xABC)
            second = proc._get_or_create_state(0xDEF)

        assert first.thread_id == "call-1"
        assert second.thread_id is None
        assert proc._trace_by_thread["call-1"] == 0xABC

    def test_set_thread_id_injected(self):
        proc = _processor()
        set_thread_id("conv-9")
        proc.on_start(_make_span("job_entrypoint", parent=None))
        span = _make_span("agent_turn", {"lk.user_input": "x"}, span_id=0x2)
        proc.on_end(span)
        exported = proc.downstream.on_end.call_args.args[0]
        assert exported._attributes["langsmith.metadata.thread_id"] == "conv-9"

    def test_thread_id_survives_out_of_context_end(self):
        # OTel may end spans in a detached task where the set_thread_id
        # ContextVar is invisible. on_start captures it (in context) keyed by
        # trace, so spans still get the id at export. Clearing the ContextVar
        # between on_start and on_end simulates that detached end.
        proc = _processor()
        tid = 0xABC
        set_thread_id("conv-9")
        proc.on_start(_make_span("job_entrypoint", parent=None, trace_id=tid))
        set_thread_id(None)
        proc.on_end(
            _make_span("agent_turn", {"lk.user_input": "x"}, trace_id=tid, span_id=0x2)
        )
        exported = proc.downstream.on_end.call_args.args[0]
        assert exported._attributes["langsmith.metadata.thread_id"] == "conv-9"


class TestMessageFromEvent:
    """Tool calls are forwarded in their OpenAI shape (LangSmith renders them)."""

    def _event(self, **attributes):
        event = MagicMock()
        event.attributes = attributes
        return event

    def test_build_assistant_tool_call_message(self):
        assert build_assistant_tool_call_message("call_1", "lookup", '{"q": "x"}') == {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "arguments": '{"q": "x"}',
                    },
                }
            ],
        }

    def test_tool_calls_forwarded_unchanged(self):
        call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"q": "x"}'},
        }
        msg = build_message_from_event(
            "assistant", self._event(role="assistant", tool_calls=[call])
        )
        assert msg["tool_calls"] == [call]

    def test_tool_calls_json_string_parsed_to_object(self):
        call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }
        msg = build_message_from_event(
            "assistant", self._event(tool_calls=[json.dumps(call)])
        )
        assert msg["tool_calls"] == [call]

    def test_unparseable_tool_call_dropped(self):
        msg = build_message_from_event(
            "assistant", self._event(tool_calls=["not json"])
        )
        assert "tool_calls" not in msg

    def test_tool_result_carries_id_and_name(self):
        msg = build_message_from_event(
            "tool", self._event(content="done", id="call_1", name="lookup")
        )
        assert msg["tool_call_id"] == "call_1"
        assert msg["name"] == "lookup"


class TestProviderAttribution:
    """LiveKit provider → normalized `gen_ai.system` (LangSmith's cost key)."""

    @staticmethod
    def _exported(proc):
        return proc.downstream.on_end.call_args.args[0]._attributes

    def test_normalize_provider_substring_and_host(self):
        assert normalize_provider("api.openai.com") == "openai"
        assert normalize_provider("beta.anthropic.com") == "anthropic"
        assert normalize_provider("https://api.deepgram.com/v1") == "deepgram"
        assert normalize_provider("cartesia") == "cartesia"
        # No known slug → host, stripped of scheme/path.
        assert normalize_provider("https://my-proxy.internal/x") == "my-proxy.internal"
        # Empty / placeholder → None (never stamp a non-matching provider).
        assert normalize_provider("unknown") is None
        assert normalize_provider(None) is None

    def test_llm_provider_host_is_normalized(self):
        # LiveKit's OpenAI plugin reports the api.openai.com host; it must become
        # the `openai` slug or LangSmith can't match a price.
        proc = _processor()
        span = _make_span("llm_request", {"gen_ai.system": "api.openai.com"})
        proc.on_end(span)
        assert self._exported(proc)["gen_ai.system"] == "openai"

    def test_export_normalizes_provider_on_any_span(self):
        # A span that skips the per-stage handlers still gets its provider
        # normalized at export (the universal _pre_export pass).
        proc = _processor()
        span = _make_span("some_other_node", {"gen_ai.system": "api.openai.com"})
        proc.on_end(span)
        assert self._exported(proc)["gen_ai.system"] == "openai"

    def test_stt_gen_ai_system_host_normalized_without_metrics(self):
        # Real trace shape: the user_turn STT span carries
        # gen_ai.system=api.openai.com and NO lk.stt_metrics; it must still
        # resolve to the openai slug (ingestion maps gen_ai.system -> ls_provider).
        proc = _processor()
        span = _make_span(
            "user_turn",
            {"lk.user_transcript": "hi", "gen_ai.system": "api.openai.com"},
        )
        proc.on_end(span)
        assert self._exported(proc)["gen_ai.system"] == "openai"

    def test_stt_gen_ai_provider_name_host_normalized(self):
        # livekit-agents >=1.5 sets the STT provider as gen_ai.provider.name (the
        # API host); it must resolve to the openai slug on both provider keys.
        proc = _processor()
        span = _make_span(
            "user_turn",
            {
                "lk.user_transcript": "hi",
                "gen_ai.request.model": "gpt-4o-mini-transcribe",
                "gen_ai.provider.name": "api.openai.com",
            },
        )
        proc.on_end(span)
        attrs = self._exported(proc)
        assert attrs["gen_ai.provider.name"] == "openai"
        assert attrs["gen_ai.system"] == "openai"


class TestUsageCapture:
    """Token/usage lifting for cost tracking (LLM cache detail, realtime)."""

    @staticmethod
    def _exported(proc):
        return proc.downstream.on_end.call_args.args[0]._attributes

    def test_llm_usage_lifted_from_metrics_blob(self):
        # The whole LLM usage — counts + cache_read detail — is read from the
        # metrics blob and written to the usage_metadata blob.
        proc = _processor()
        metrics = json.dumps(
            {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
                "prompt_cached_tokens": 30,
            }
        )
        span = _make_span("llm_request", {"lk.llm_metrics": metrics})
        proc.on_end(span)
        usage = json.loads(self._exported(proc)["langsmith.usage_metadata"])
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 40
        assert usage["total_tokens"] == 140
        assert usage["input_token_details"] == {"cache_read": 30}

    def test_orphaned_realtime_metrics_span_carries_usage(self):
        # An orphaned realtime_metrics span carries the model usage itself; its
        # audio/cached detail must be priced (as audio, not text).
        proc = _processor()
        blob = json.dumps(
            {
                "input_tokens": 200,
                "output_tokens": 80,
                "total_tokens": 280,
                "input_token_details": {"audio_tokens": 150, "cached_tokens": 20},
                "output_token_details": {"audio_tokens": 60},
            }
        )
        proc.on_end(_make_span("realtime_metrics", {"lk.realtime_model_metrics": blob}))
        attrs = self._exported(proc)
        assert attrs["langsmith.span.kind"] == "llm"
        # Usage rides on langsmith.usage_metadata (JSON) — the only OTel path that
        # carries per-modality detail; flat gen_ai.usage.* detail is dropped.
        usage = json.loads(attrs["langsmith.usage_metadata"])
        assert usage["input_tokens"] == 200
        assert usage["output_tokens"] == 80
        assert usage["input_token_details"] == {"audio": 150, "cache_read": 20}
        assert usage["output_token_details"] == {"audio": 60}

    def test_realtime_usage_lifted_when_stamped_on_active_span(self):
        # livekit-agents (>=1.6) stamps realtime metrics directly on the active
        # agent_turn span when it's still recording — no realtime_metrics child.
        # The audio/cache detail must still be lifted, wherever the blob lands.
        proc = _processor()
        blob = json.dumps(
            {
                "input_tokens": 200,
                "output_tokens": 80,
                "total_tokens": 280,
                "input_token_details": {"audio_tokens": 150, "cached_tokens": 20},
                "output_token_details": {"audio_tokens": 60},
            }
        )
        span = _make_span(
            "agent_turn",
            {
                "lk.response.text": "hi",
                "lk.realtime_model_metrics": blob,
                # livekit sets the aggregate counts on the span too; only the
                # audio/cache detail needs recovering.
                "gen_ai.usage.input_tokens": 200,
                "gen_ai.usage.output_tokens": 80,
            },
        )
        proc.on_end(span)
        attrs = self._exported(proc)
        # A realtime turn is the model call itself → llm span (carries the cost).
        assert attrs["langsmith.span.kind"] == "llm"
        usage = json.loads(attrs["langsmith.usage_metadata"])
        assert usage["input_token_details"] == {"audio": 150, "cache_read": 20}
        assert usage["output_token_details"] == {"audio": 60}

    def test_cascade_agent_turn_stays_chain(self):
        # A cascade turn only wraps the STT/LLM/TTS children (which carry usage),
        # so it must stay a chain — an llm kind here would double-count cost.
        proc = _processor()
        span = _make_span(
            "agent_turn", {"lk.user_input": "hi", "lk.response.text": "hello"}
        )
        proc.on_end(span)
        assert self._exported(proc)["langsmith.span.kind"] == "chain"
