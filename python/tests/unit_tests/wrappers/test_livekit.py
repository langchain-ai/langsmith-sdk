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
        completion = json.loads(root._attributes["gen_ai.completion"])
        assert completion[0]["content"] == "sunny"
        # Per-conversation state freed after release.
        assert len(proc._deferred_root_spans) == 0
        assert len(proc._conversation_by_trace) == 0


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
            json.loads(root._attributes["gen_ai.completion"])[0]["content"] == "sunny"
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
        assert [m["content"] for m in proc._conversation_by_trace[tid]] == [
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


class TestStageAndRealtimeUsage:
    """STT/TTS billed quantities and realtime audio detail -> gen_ai.usage."""

    @staticmethod
    def _exported(proc):
        return proc.downstream.on_end.call_args.args[0]._attributes

    def test_stt_audio_duration_becomes_usage(self):
        proc = _processor()
        metrics = json.dumps(
            {
                "audio_duration": 4.6,
                "metadata": {"model_provider": "deepgram", "model_name": "nova-3"},
            }
        )
        span = _make_span(
            "user_turn",
            {
                "lk.user_transcript": "hi",
                "lk.stt_metrics": metrics,
                "gen_ai.request.model": "nova-3",
            },
        )
        proc.on_end(span)
        attrs = self._exported(proc)
        assert attrs["gen_ai.usage.input_tokens"] == 5  # round(4.6) seconds
        assert attrs["langsmith.metadata.usage_unit"] == "audio_seconds"
        # Provider is stamped as gen_ai.system by _stamp_provider.
        assert attrs["gen_ai.system"] == "deepgram"

    def test_stt_model_name_falls_back_to_metrics_metadata(self):
        # Without gen_ai.request.model on the span, the model name must come from
        # the metric's metadata -- else LangSmith can't match the custom price.
        proc = _processor()
        metrics = json.dumps(
            {
                "audio_duration": 2.0,
                "metadata": {"model_provider": "deepgram", "model_name": "nova-3"},
            }
        )
        span = _make_span(
            "user_turn", {"lk.user_transcript": "hi", "lk.stt_metrics": metrics}
        )
        proc.on_end(span)
        attrs = self._exported(proc)
        assert attrs["langsmith.metadata.model_name"] == "nova-3"
        assert attrs["gen_ai.request.model"] == "nova-3"

    def test_tts_character_count_becomes_usage(self):
        proc = _processor()
        metrics = json.dumps(
            {
                "characters_count": 128,
                "metadata": {"model_provider": "cartesia", "model_name": "sonic"},
            }
        )
        span = _make_span(
            "tts_request", {"lk.input_text": "hello", "lk.tts_metrics": metrics}
        )
        proc.on_end(span)
        attrs = self._exported(proc)
        assert attrs["gen_ai.usage.output_tokens"] == 128
        assert attrs["langsmith.metadata.usage_unit"] == "characters"
        assert attrs["gen_ai.system"] == "cartesia"

    def test_stt_without_metrics_emits_no_usage(self):
        proc = _processor()
        span = _make_span("user_turn", {"lk.user_transcript": "hi"})
        proc.on_end(span)
        assert "gen_ai.usage.input_tokens" not in self._exported(proc)

    def test_realtime_audio_detail_lifted_onto_turn(self):
        proc = _processor()
        rt_metrics = json.dumps(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "input_token_details": {"audio_tokens": 80, "cached_tokens": 10},
                "output_token_details": {"audio_tokens": 45},
            }
        )
        # realtime_metrics span is suppressed; its data caches under its parent.
        rt = _make_span(
            "realtime_metrics",
            {"lk.realtime_model_metrics": rt_metrics},
            span_id=0x99,
        )
        rt.parent.span_id = 0x55
        proc.on_end(rt)
        proc.downstream.on_end.assert_not_called()  # suppressed
        # The agent_turn (same span id as the metrics' parent) drains it.
        turn = _make_span("agent_turn", {}, span_id=0x55)
        proc.on_end(turn)
        attrs = self._exported(proc)
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.input_token_details"] == str(
            {"audio": 80, "cache_read": 10}
        )
        assert attrs["gen_ai.usage.output_token_details"] == str({"audio": 45})


class TestProviderAttribution:
    """LiveKit provider -> normalized gen_ai.system (LangSmith's cost key)."""

    @staticmethod
    def _exported(proc):
        return proc.downstream.on_end.call_args.args[0]._attributes

    def test_normalize_provider_substring_and_host(self):
        assert _normalize_provider("api.openai.com") == "openai"
        assert _normalize_provider("beta.anthropic.com") == "anthropic"
        assert _normalize_provider("https://api.deepgram.com/v1") == "deepgram"
        assert _normalize_provider("cartesia") == "cartesia"
        # No known slug -> host, stripped of scheme/path.
        assert _normalize_provider("https://my-proxy.internal/x") == "my-proxy.internal"
        # Empty / placeholder -> None (never stamp a non-matching provider).
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
        # the openai slug or LangSmith can't match a price.
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
