"""Unit tests for the LiveKit voice tracing integration.

Pure unit tests: the ``LiveKitLangSmithSpanProcessor`` imports only
``opentelemetry`` (+ the shared base), never ``livekit-agents``, so spans are
mocked and no framework install is needed.
"""

import base64
import json
from unittest.mock import MagicMock

from langsmith._internal.voice import set_thread_id
from langsmith.integrations.livekit.processor import (
    LiveKitLangSmithSpanProcessor,
    _normalize_provider,
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


class TestDispatchDisposition:
    """``_dispatch`` decides whether the base exports each span."""

    def test_normal_span_exported(self):
        proc = _processor()
        span = _make_span("user_turn", {"lk.user_transcript": "hi"})
        proc.on_end(span)
        proc.downstream.on_end.assert_called_once()

    def test_realtime_metrics_suppressed(self):
        proc = _processor()
        span = _make_span("realtime_metrics", {"lk.realtime_model_metrics": "{}"})
        proc.on_end(span)
        proc.downstream.on_end.assert_not_called()

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
        assert len(proc._deferred_root_spans) == 0


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
        completion = json.loads(root._attributes["gen_ai.completion"])["messages"]
        assert completion[0]["content"] == "sunny"
        # Per-conversation state freed after release.
        assert len(proc._deferred_root_spans) == 0
        assert len(proc._conversation_by_trace) == 0


class TestRealtimeUserTranscript:
    """Realtime (speech-to-speech) user transcripts fed via instrument_session.

    In the realtime pipeline there is no STT ``user_turn`` span; LiveKit emits a
    bare ``user_speaking`` span and delivers the transcript out of band via the
    ``user_input_transcribed`` event. The host forwards it to the processor, which
    holds the span open until the transcript arrives, then stamps it on.
    """

    def _speaking(self, *, thread="call-1", trace_id=0xABC, span_id=0x2):
        return _make_span(
            "user_speaking",
            {"langsmith.metadata.thread_id": thread},
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
        proc.on_end(self._speaking())
        # Held open — nothing exported yet.
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
        assert len(proc._deferred_user_speaking) == 0
        assert len(proc._pending_user_transcripts) == 0

    def test_transcript_before_span_is_buffered(self):
        # Transcript can race ahead of the span's on_end — buffer, then apply.
        proc = _processor()
        proc._record_user_transcript("call-1", "hello there")
        assert self._exported(proc, "user_speaking") == []

        proc.on_end(self._speaking())

        exported = self._exported(proc, "user_speaking")
        assert len(exported) == 1
        assert exported[0]._attributes["lk.user_transcript"] == "hello there"
        assert len(proc._pending_user_transcripts) == 0

    def test_fifo_pairing_within_conversation(self):
        # Two utterances, two transcripts — paired in order.
        proc = _processor()
        proc.on_end(self._speaking(span_id=0x2))
        proc.on_end(self._speaking(span_id=0x3))
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
        proc.on_end(self._speaking())
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
        proc.on_end(
            _make_span(
                "job_entrypoint",
                {"langsmith.metadata.thread_id": "call-1"},
                parent=None,
                trace_id=tid,
            )
        )
        proc.on_end(self._speaking(trace_id=tid))
        assert self._exported(proc, "user_speaking") == []  # held

        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))

        assert len(self._exported(proc, "user_speaking")) == 1
        assert len(proc._deferred_user_speaking) == 0

    def test_shutdown_flushes_untranscribed_span(self):
        proc = _processor()
        proc.on_end(self._speaking())
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
        proc = _processor()
        tid = 0xABC
        proc.on_end(
            _make_span(
                "job_entrypoint",
                {"langsmith.metadata.thread_id": "call-1"},
                parent=None,
                trace_id=tid,
            )
        )
        # User speaks (early span), then the reply turn lands and is recorded...
        proc.on_end(
            _make_span(
                "user_speaking",
                {"langsmith.metadata.thread_id": "call-1"},
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

        root = self._root(proc)
        # Input = the user's opening turn; output = the assistant reply.
        assert json.loads(root._attributes["gen_ai.prompt"]) == {
            "messages": [{"role": "user", "content": "weather?"}]
        }
        assert (
            json.loads(root._attributes["gen_ai.completion"])["messages"][0]["content"]
            == "sunny"
        )

    def test_greeting_then_user_turn_ordered(self):
        # Agent greets first (agent_turn, no user_speaking), then a user turn.
        # The greeting must not steal the user's transcript, and order holds.
        proc = _processor()
        tid = 0xABC
        proc.on_end(
            _make_span(
                "job_entrypoint",
                {"langsmith.metadata.thread_id": "call-1"},
                parent=None,
                trace_id=tid,
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
                {"langsmith.metadata.thread_id": "call-1"},
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

        root = self._root(proc)
        contents = [
            m["content"]
            for m in json.loads(root._attributes["gen_ai.prompt"])["messages"]
        ]
        contents += [
            m["content"]
            for m in json.loads(root._attributes["gen_ai.completion"])["messages"]
        ]
        assert contents == ["hi there!", "weather?", "sunny"]


class TestAgentTurnKind:
    """agent_turn is llm in realtime (it IS the inference), chain in cascade."""

    def _turn_kind(self, attributes):
        proc = _processor()
        proc.on_end(_make_span("agent_turn", attributes, span_id=0x2))
        exported = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0].name == "agent_turn"
        )
        return exported._attributes["langsmith.span.kind"]

    def test_realtime_turn_is_llm(self):
        # A realtime turn carries lk.realtime_model_metrics (drained from its
        # realtime_metrics child) — no child llm_request, so the turn itself is
        # the inference node.
        assert (
            self._turn_kind(
                {"lk.response.text": "sunny", "lk.realtime_model_metrics": "{}"}
            )
            == "llm"
        )

    def test_cascade_turn_is_chain(self):
        # Cascade turn carries user_input/response but no realtime metrics (the
        # real inference is the child llm_request span) — it's just a container.
        assert (
            self._turn_kind({"lk.user_input": "weather?", "lk.response.text": "sunny"})
            == "chain"
        )

    def test_response_function_calls_render_as_tool_calls(self):
        # A realtime turn whose reply is a tool call must show the tool call on
        # the assistant completion, not an empty/text-only output.
        proc = _processor()
        fcs = json.dumps(
            [
                {
                    "call_id": "call_1",
                    "name": "lookup_weather",
                    "arguments": '{"city":"x"}',
                }
            ]
        )
        proc.on_end(
            _make_span(
                "agent_turn",
                {"lk.response.function_calls": fcs, "lk.realtime_model_metrics": "{}"},
                span_id=0x2,
            )
        )
        turn = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0].name == "agent_turn"
        )
        msg = json.loads(turn._attributes["gen_ai.completion"])["messages"][0]
        assert msg["tool_calls"] == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "lookup_weather", "arguments": '{"city":"x"}'},
            }
        ]


class TestInstrumentSession:
    """instrument_session subscribes the SDK to a session's events itself."""

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

    def _instrument(self, session, thread_id, proc):
        proc.instrument_session(session, thread_id)

    def test_final_transcript_wired_to_processor(self):
        proc = _processor()
        session = self._FakeSession()
        self._instrument(session, "call-1", proc)

        proc.on_end(
            _make_span(
                "user_speaking",
                {"langsmith.metadata.thread_id": "call-1"},
                span_id=0x2,
            )
        )
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
        self._instrument(session, "call-1", proc)

        session.handlers["user_input_transcribed"](
            self._event(is_final=False, transcript="partial")
        )
        # Interim result buffered nothing; a later span has no transcript to pair.
        assert len(proc._pending_user_transcripts) == 0


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
        assert format(tid, "032x") in proc._deferred_root_spans

        # When the session finally ends, the complete root is exported once.
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))
        root = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0]._attributes.get("langsmith.root_span")
        )
        assert (
            json.loads(root._attributes["gen_ai.completion"])["messages"][0]["content"]
            == "sunny"
        )

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


class TestEgressRecording:
    """expect_recording / complete_recording hold the root for late egress audio."""

    def test_expect_holds_until_complete_with_audio(self):
        proc = _processor()
        tid = 0xABC
        proc.expect_recording("call-1")
        proc.on_end(
            _make_span(
                "job_entrypoint",
                {"langsmith.metadata.thread_id": "call-1"},
                parent=None,
                trace_id=tid,
            )
        )
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))
        # Session ended but recording still awaited → root NOT exported.
        assert not any(
            c.args[0]._attributes.get("langsmith.root_span")
            for c in proc.downstream.on_end.call_args_list
        )

        proc.complete_recording("call-1", b"OggS-bytes", name="call.ogg")

        root = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0]._attributes.get("langsmith.root_span")
        )
        payload = json.loads(root._attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"OggS-bytes"

    def test_complete_with_none_releases_without_audio(self):
        proc = _processor()
        tid = 0xABC
        proc.expect_recording("call-1")
        proc.on_end(
            _make_span(
                "job_entrypoint",
                {"langsmith.metadata.thread_id": "call-1"},
                parent=None,
                trace_id=tid,
            )
        )
        proc.on_end(_make_span("agent_session", trace_id=tid, span_id=0x3))
        proc.complete_recording("call-1", None)

        root = next(
            c.args[0]
            for c in proc.downstream.on_end.call_args_list
            if c.args[0]._attributes.get("langsmith.root_span")
        )
        assert "langsmith.attachments" not in root._attributes


class TestStateTTL:
    """Per-conversation state is TTL-bounded so abandoned calls cannot leak."""

    def test_abandoned_state_expires(self):
        # A conversation whose session never ends must not leak; a zero TTL
        # drops it on the next write to that cache.
        proc = _processor(state_ttl_seconds=0)
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=0xAAA))
        # A later, different conversation's root triggers eviction of the first.
        proc.on_end(_make_span("job_entrypoint", parent=None, trace_id=0xBBB))
        assert format(0xAAA, "032x") not in proc._deferred_root_spans

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
        # Store holds (sort_key, seq, message) tuples.
        assert [m["content"] for _, m in proc._conversation_by_trace[tid]] == [
            "one",
            "two",
        ]


class TestThreadId:
    """Thread id is injected from the per-context ``set_thread_id``."""

    def teardown_method(self):
        set_thread_id(None)

    def test_set_thread_id_injected(self):
        proc = _processor()
        set_thread_id("conv-9")
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

    def test_tool_calls_forwarded_unchanged(self):
        proc = _processor()
        call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"q": "x"}'},
        }
        msg = proc._message_from_event(
            "assistant", self._event(role="assistant", tool_calls=[call])
        )
        assert msg["tool_calls"] == [call]

    def test_tool_calls_json_string_parsed_to_object(self):
        proc = _processor()
        call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }
        msg = proc._message_from_event(
            "assistant", self._event(tool_calls=[json.dumps(call)])
        )
        assert msg["tool_calls"] == [call]

    def test_unparseable_tool_call_dropped(self):
        proc = _processor()
        msg = proc._message_from_event(
            "assistant", self._event(tool_calls=["not json"])
        )
        assert "tool_calls" not in msg

    def test_tool_result_carries_id_and_name(self):
        proc = _processor()
        msg = proc._message_from_event(
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
        assert _normalize_provider("api.openai.com") == "openai"
        assert _normalize_provider("beta.anthropic.com") == "anthropic"
        assert _normalize_provider("https://api.deepgram.com/v1") == "deepgram"
        assert _normalize_provider("cartesia") == "cartesia"
        # No known slug → host, stripped of scheme/path.
        assert _normalize_provider("https://my-proxy.internal/x") == "my-proxy.internal"
        # Empty / placeholder → None (never stamp a non-matching provider).
        assert _normalize_provider("unknown") is None
        assert _normalize_provider(None) is None

    def test_stt_provider_from_metrics_metadata(self):
        proc = _processor()
        metrics = json.dumps({"metadata": {"model_provider": "deepgram"}})
        span = _make_span(
            "user_turn", {"lk.user_transcript": "hi", "lk.stt_metrics": metrics}
        )
        proc.on_end(span)
        assert self._exported(proc)["gen_ai.system"] == "deepgram"

    def test_llm_provider_host_is_normalized(self):
        # LiveKit's OpenAI plugin reports the api.openai.com host; it must become
        # the `openai` slug or LangSmith can't match a price.
        proc = _processor()
        span = _make_span("llm_request", {"gen_ai.system": "api.openai.com"})
        proc.on_end(span)
        assert self._exported(proc)["gen_ai.system"] == "openai"

    def test_stt_provider_host_is_normalized(self):
        # The demo's STT is OpenAI, so LiveKit reports the api.openai.com host on
        # the user_turn span; it must resolve to the openai slug.
        proc = _processor()
        metrics = json.dumps({"metadata": {"model_provider": "api.openai.com"}})
        span = _make_span(
            "user_turn", {"lk.user_transcript": "hi", "lk.stt_metrics": metrics}
        )
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
