"""Unit tests for the Pipecat voice tracing integration.

Covers everything shipped in the Pipecat PR: the ``PipecatLangSmithSpanProcessor``
span rewriting, the shared ``BaseLangSmithSpanProcessor`` helpers, and the
``voice.audio`` utilities. These are pure unit tests — they mock the OTel
``ReadableSpan`` and the downstream processor, so no ``pipecat-ai`` install is
required (only ``opentelemetry-sdk``, a dev dependency).
"""

import base64
import io
import json
import sys
import wave
from unittest.mock import MagicMock, patch

import pytest

from langsmith._internal._beta_decorator import LangSmithBetaWarning, _warn_once
from langsmith._internal.voice import audio as audio_utils
from langsmith._internal.voice import set_thread_id, thread_id_from_context
from langsmith._internal.voice.base_span_processor import (
    DEFAULT_AUDIO_SIZE_LIMIT,
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)
from langsmith.integrations.pipecat.processor import (
    PipecatLangSmithSpanProcessor,
    _AudioRecord,
)


def _make_span(name: str, attributes: dict | None = None, trace_id: int = 0x1):
    """Build a mock span for the processor.

    The processor only *reads* ``span.attributes`` (and a few read-only fields);
    it never mutates the span. Translation accumulates on a ``TranslatedSpan``
    draft, and a fresh span is built for export — so the rewritten attributes are
    read off the exported span (see :func:`_exported_attrs`), not this input. The
    remaining ``ReadableSpan`` fields are auto-mocked, which is all
    ``TranslatedSpan.finalize`` needs to construct the export span.
    """
    span = MagicMock()
    span.name = name
    span.attributes = dict(attributes or {})
    span.context = MagicMock()
    span.context.trace_id = trace_id
    span.events = []
    return span


def _processor(**kwargs) -> PipecatLangSmithSpanProcessor:
    """Processor wired to a mock downstream so nothing is exported for real."""
    return PipecatLangSmithSpanProcessor(downstream_processor=MagicMock(), **kwargs)


def _exported_attrs(proc) -> dict:
    """Attributes of the (last) finalized span the processor forwarded downstream.

    The processor never mutates the incoming span; it accumulates the translation
    on a ``TranslatedSpan`` and forwards a freshly built span. So the rewritten
    attributes are read off that exported span, not the input.
    """
    assert proc.downstream.on_end.called, "nothing was exported downstream"
    exported = proc.downstream.on_end.call_args.args[0]
    return dict(exported.attributes or {})


class TestPipecatDispatch:
    """Span classification, rewriting, and unconditional export."""

    def test_stt_span(self):
        proc = _processor()
        span = _make_span("stt", {"transcript": "hello there"})

        proc.on_end(span)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "llm"
        prompt = json.loads(attrs["gen_ai.prompt"])["messages"]
        completion = json.loads(attrs["gen_ai.completion"])["messages"]
        assert prompt[0]["content"] == 'Audio for: "hello there"'
        assert completion[0]["content"] == "hello there"
        # STT/TTS spans stay in the tree but are dropped from the Messages view.
        assert attrs["langsmith.metadata.ls_message_view_exclude"] is True
        proc.downstream.on_end.assert_called_once()

    def test_stt_span_without_transcript_has_no_completion(self):
        proc = _processor()
        span = _make_span("stt", {})

        proc.on_end(span)

        assert "gen_ai.completion" not in _exported_attrs(proc)

    def test_tts_span(self):
        proc = _processor()
        span = _make_span("tts", {"text": "hi", "voice_id": "voice-1"})

        proc.on_end(span)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "llm"
        assert attrs["langsmith.metadata.voice_id"] == "voice-1"
        assert json.loads(attrs["gen_ai.prompt"])["messages"][0]["content"] == "hi"
        assert (
            json.loads(attrs["gen_ai.completion"])["messages"][0]["content"]
            == 'Generated audio for: "hi"'
        )
        assert attrs["langsmith.metadata.ls_message_view_exclude"] is True

    def test_turn_span(self):
        proc = _processor()
        span = _make_span("turn", {"turn.number": 3, "turn.was_interrupted": True})

        proc.on_end(span)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "chain"
        assert attrs["langsmith.metadata.turn_number"] == 3
        assert attrs["langsmith.metadata.turn_was_interrupted"] is True

    def test_llm_span_default_kind_and_message_normalization(self):
        proc = _processor()
        context = [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "what is 2+2?"},
        ]
        span = _make_span("llm", {"input": json.dumps(context), "output": "4"})

        proc.on_end(span)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "llm"
        assert json.loads(attrs["gen_ai.prompt"])["messages"][-1]["content"] == (
            "what is 2+2?"
        )
        assert json.loads(attrs["gen_ai.completion"])["messages"][0]["content"] == "4"

    def test_llm_input_messages_passed_through_verbatim(self):
        # The request history is forwarded in the LLM provider's own message
        # format, not rewritten — so the trace mirrors what the model was sent.
        proc = _processor()
        context = [
            {"role": "user", "content": "weather?"},
            {"role": "assistant", "content": [{"type": "text", "text": "checking"}]},
        ]
        span = _make_span("llm", {"input": json.dumps(context), "output": "sunny"})

        proc.on_end(span)

        prompt = json.loads(_exported_attrs(proc)["gen_ai.prompt"])
        assert prompt["messages"] == context

    def test_llm_span_kind_override(self):
        proc = _processor(llm_span_kind="chain")
        span = _make_span("llm", {"input": "[]", "output": ""})

        proc.on_end(span)

        assert _exported_attrs(proc)["langsmith.span.kind"] == "chain"

    def test_llm_completion_plain_text_stays_text(self):
        # A JSON-decodable scalar must NOT be treated as a structured message.
        proc = _processor()
        span = _make_span("llm", {"input": "[]", "output": "4"})

        proc.on_end(span)

        completion = json.loads(_exported_attrs(proc)["gen_ai.completion"])
        assert completion["messages"][0] == {"role": "assistant", "content": "4"}

    def test_llm_completion_preserves_tool_calls(self):
        # When the framework emits the structured response with tool_calls, the
        # message is forwarded unchanged in its OpenAI shape (LangSmith ingest
        # renders it) rather than flattened to a string.
        proc = _processor()
        output = json.dumps(
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"q": "x"}'},
                    }
                ],
            }
        )
        span = _make_span("llm", {"input": "[]", "output": output})

        proc.on_end(span)

        completion = json.loads(_exported_attrs(proc)["gen_ai.completion"])
        msg = completion["messages"][0]
        assert msg["role"] == "assistant"
        assert msg["tool_calls"][0] == {
            "id": "call_1",
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"q": "x"}'},
        }

    def test_conversation_span_renders_root(self):
        proc = _processor()
        trace_id = 0xABC
        # An llm span first populates the per-trace conversation snapshot...
        llm = _make_span(
            "llm",
            {
                "input": json.dumps([{"role": "user", "content": "hi"}]),
                "output": "hello",
            },
            trace_id=trace_id,
        )
        proc.on_end(llm)
        # ...then the conversation span renders it onto the root.
        convo = _make_span("conversation", {"conversation.id": "c1"}, trace_id=trace_id)

        proc.on_end(convo)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "chain"
        assert attrs["langsmith.root_span"] is True
        assert attrs["langsmith.metadata.ls_modality"] == "audio"
        # The root is attributed to this integration so usage is trackable.
        assert attrs["langsmith.metadata.ls_integration"] == "pipecat"
        # The whole transcript lands on the root's input (like the livekit root).
        prompt = json.loads(attrs["gen_ai.prompt"])
        assert [m["content"] for m in prompt["messages"]] == ["hi", "hello"]
        assert "gen_ai.completion" not in attrs
        # Per-trace state is cleaned up once the root is rendered.
        assert trace_id not in proc._transcript_by_trace

    def test_unknown_span_passed_through_untouched_but_exported(self):
        proc = _processor()
        span = _make_span("model", {"some.attr": "x"})

        proc.on_end(span)

        assert "langsmith.span.kind" not in _exported_attrs(proc)
        proc.downstream.on_end.assert_called_once()


class TestPipecatRealtimeHistory:
    """OpenAI realtime ``llm_request`` carries the authoritative history snapshot."""

    def test_llm_request_snapshots_history_including_tools(self):
        # The llm_request span's `input` is the full context — including the
        # assistant tool call and the tool result — so the conversation root
        # renders them. The spoken reply arrives on llm_response and is appended.
        proc = _processor()
        trace_id = 0xDEF
        history = [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "weather?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city":"SF"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": '{"temp": 68}'},
        ]
        req = _make_span(
            "llm_request", {"input": json.dumps(history)}, trace_id=trace_id
        )
        proc.on_end(req)
        # The llm_request span itself stays a chain wrapper (usage is on response).
        assert _exported_attrs(proc)["langsmith.span.kind"] == "chain"

        resp = _make_span("llm_response", {"output": "it's 68"}, trace_id=trace_id)
        proc.on_end(resp)

        convo = _make_span("conversation", {"conversation.id": "c"}, trace_id=trace_id)
        proc.on_end(convo)

        prompt = json.loads(_exported_attrs(proc)["gen_ai.prompt"])["messages"]
        assert [m["role"] for m in prompt] == ["user", "assistant", "tool", "assistant"]
        assert prompt[1]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert prompt[2]["content"] == '{"temp": 68}'  # tool result rendered
        assert prompt[3]["content"] == "it's 68"  # spoken reply appended

    def test_llm_request_replaces_accumulated_transcript(self):
        # A stray STT-fold is overwritten by the authoritative snapshot — no
        # duplicated user turn.
        proc = _processor()
        tid = 0x1
        proc.on_end(
            _make_span("stt", {"transcript": "hi", "is_final": True}, trace_id=tid)
        )
        snapshot = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        proc.on_end(
            _make_span("llm_request", {"input": json.dumps(snapshot)}, trace_id=tid)
        )
        proc.on_end(_make_span("conversation", {"conversation.id": "c"}, trace_id=tid))

        prompt = json.loads(_exported_attrs(proc)["gen_ai.prompt"])["messages"]
        assert [m["content"] for m in prompt] == ["hi", "hello"]

    def test_cascade_llm_handling_unchanged(self):
        # Cascade emits `llm`, never `llm_request`; its snapshot+append behavior
        # is untouched by the realtime path.
        proc = _processor()
        tid = 0x1
        proc.on_end(
            _make_span(
                "llm",
                {
                    "input": json.dumps([{"role": "user", "content": "q"}]),
                    "output": "a",
                },
                trace_id=tid,
            )
        )
        proc.on_end(_make_span("conversation", {"conversation.id": "c"}, trace_id=tid))

        prompt = json.loads(_exported_attrs(proc)["gen_ai.prompt"])["messages"]
        assert [m["content"] for m in prompt] == ["q", "a"]


class TestPipecatToolCalls:
    """Realtime tool spans: ``llm_tool_call`` + ``llm_tool_result`` merge to one run."""

    @staticmethod
    def _exported_spans(proc) -> list:
        """Every finalized span forwarded downstream, in order."""
        return [c.args[0] for c in proc.downstream.on_end.call_args_list]

    def test_call_and_result_merge_into_one_span(self):
        # Pipecat puts no usable id on the result span, so pairing is by order.
        proc = _processor()
        trace_id = 0xABC
        call = _make_span(
            "llm_tool_call",
            {"tool.function_name": "get_weather", "tool.arguments": '{"city": "SF"}'},
            trace_id=trace_id,
        )

        # The call span is held (deferred) until its result arrives.
        proc.on_end(call)
        assert not proc.downstream.on_end.called

        result = _make_span(
            "llm_tool_result",
            {"tool.result": '{"temp": 68}', "tool.result_status": "completed"},
            trace_id=trace_id,
        )
        result.end_time = 999

        proc.on_end(result)

        # One span exported: the merged call span; the result span is dropped.
        exported = self._exported_spans(proc)
        assert len(exported) == 1
        span = exported[0]
        attrs = dict(span.attributes)
        assert attrs["langsmith.span.kind"] == "tool"
        assert span.name == "get_weather"
        assert attrs["gen_ai.prompt"] == '{"city": "SF"}'
        assert attrs["gen_ai.completion"] == '{"temp": 68}'
        assert attrs["langsmith.metadata.tool_result_status"] == "completed"
        assert span.end_time == 999  # stretched to the result's end
        assert not proc._tool_calls_by_trace

    def test_result_without_call_exported_standalone(self):
        # A result with no deferred call still surfaces as a tool run (output only).
        proc = _processor()
        result = _make_span("llm_tool_result", {"tool.result": '{"ok": true}'})

        proc.on_end(result)

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "tool"
        assert attrs["gen_ai.completion"] == '{"ok": true}'
        assert "gen_ai.prompt" not in attrs  # no args were ever seen

    def test_multiple_calls_pair_in_order(self):
        # Two sequential calls, two results: each result pairs with the oldest
        # deferred call (FIFO).
        proc = _processor()
        trace_id = 0xABC
        for name, args in (("a", '{"x": 1}'), ("b", '{"y": 2}')):
            proc.on_end(
                _make_span(
                    "llm_tool_call",
                    {"tool.function_name": name, "tool.arguments": args},
                    trace_id=trace_id,
                )
            )
        for res in ('"A"', '"B"'):
            proc.on_end(
                _make_span("llm_tool_result", {"tool.result": res}, trace_id=trace_id)
            )

        exported = self._exported_spans(proc)
        by_name = {s.name: dict(s.attributes) for s in exported}
        assert by_name["a"]["gen_ai.prompt"] == '{"x": 1}'
        assert by_name["a"]["gen_ai.completion"] == '"A"'
        assert by_name["b"]["gen_ai.prompt"] == '{"y": 2}'
        assert by_name["b"]["gen_ai.completion"] == '"B"'
        assert not proc._tool_calls_by_trace

    def test_orphaned_call_flushed_on_conversation_end(self):
        # A call whose result never arrives is flushed (args only) when the
        # conversation ends, not held indefinitely.
        proc = _processor()
        trace_id = 0xABC
        call = _make_span(
            "llm_tool_call",
            {"tool.function_name": "hang", "tool.arguments": "{}"},
            trace_id=trace_id,
        )
        proc.on_end(call)
        assert not proc.downstream.on_end.called

        convo = _make_span("conversation", {"conversation.id": "x"}, trace_id=trace_id)
        proc.on_end(convo)

        exported = self._exported_spans(proc)
        kinds = [dict(s.attributes).get("langsmith.span.kind") for s in exported]
        assert "tool" in kinds  # the orphaned call was flushed
        assert not proc._tool_calls_by_trace

    def test_orphaned_call_flushed_on_shutdown(self):
        proc = _processor()
        call = _make_span(
            "llm_tool_call", {"tool.function_name": "hang", "tool.arguments": "{}"}
        )
        proc.on_end(call)
        assert not proc.downstream.on_end.called

        proc.shutdown()

        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "tool"
        assert not proc._tool_calls_by_trace
        proc.downstream.shutdown.assert_called_once()


class TestPipecatAudio:
    """Audio-buffer registration, accumulation, and root attachment."""

    def test_attach_audio_buffer_registers_and_accumulates(self):
        proc = _processor()
        captured = {}

        class FakeBuffer:
            def event_handler(self, event_name):
                def register(fn):
                    captured[event_name] = fn
                    return fn

                return register

        proc.attach_audio_buffer(FakeBuffer(), "conv-1")
        handler = captured["on_audio_data"]

        # The AudioBufferProcessor emits already-merged (stereo) PCM in chunks.
        import asyncio

        asyncio.run(handler(None, b"\x01\x02\x0a\x0b", 16000, 2))
        asyncio.run(handler(None, b"\x03\x04\x0c\x0d", 16000, 2))

        rec = proc._audio_by_conversation["conv-1"]
        assert bytes(rec.pcm) == b"\x01\x02\x0a\x0b\x03\x04\x0c\x0d"
        assert rec.sample_rate == 16000
        assert rec.num_channels == 2

    def test_conversation_span_attaches_stereo_wav(self):
        proc = _processor()
        proc._accumulate_audio("c1", b"\x00\x01\x02\x03" * 8, 16000, 2)
        span = _make_span("conversation", {"conversation.id": "c1"})

        proc.on_end(span)

        payload = json.loads(_exported_attrs(proc)["langsmith.attachments"])
        assert payload[0]["name"] == "conversation.wav"
        assert payload[0]["mime_type"] == "audio/wav"
        decoded = base64.b64decode(payload[0]["content"])
        assert decoded[:4] == b"RIFF"
        with wave.open(io.BytesIO(decoded)) as wf:
            assert wf.getnchannels() == 2  # user left, bot right

    def test_mismatched_conversation_id_attaches_nothing(self):
        # A recording exists under a different id than the span carries. The
        # lookup is strictly keyed (no "only one in flight" fallback), so no
        # audio is attached — never another caller's recording.
        proc = _processor()
        proc._accumulate_audio("other-call", b"\x00\x01\x02\x03" * 8, 16000, 2)
        span = _make_span("conversation", {"conversation.id": "this-call"})

        proc.on_end(span)

        assert "langsmith.attachments" not in _exported_attrs(proc)

    def test_conversation_span_no_audio_no_attachment(self):
        proc = _processor()
        span = _make_span("conversation", {"conversation.id": "c1"})

        proc.on_end(span)

        assert "langsmith.attachments" not in _exported_attrs(proc)

    def test_accumulate_audio_truncates_before_extend(self):
        # pcm budget = 50 - 44 header = 6, rounded down to a whole stereo frame (4).
        proc = _processor(audio_size_limit_bytes=50)
        proc._accumulate_audio("c1", b"\x00\x01\x02\x03" * 8, 16000, 2)

        rec = proc._audio_by_conversation["c1"]
        assert rec.audio_truncated is True
        assert bytes(rec.pcm) == b"\x00\x01\x02\x03"

    def test_oversize_audio_skips_conversion(self):
        proc = _processor(audio_size_limit_bytes=50)
        proc._audio_by_conversation["c1"] = _AudioRecord(
            sample_rate=16000,
            num_channels=2,
            pcm=bytearray(b"\x00\x01\x02\x03" * 4),
        )
        span = _make_span("conversation", {"conversation.id": "c1"})

        with patch("langsmith.integrations.pipecat.processor.pcm_to_wav") as patched:
            proc.on_end(span)

        patched.assert_not_called()
        assert "langsmith.attachments" not in _exported_attrs(proc)


class TestBaseProcessorHelpers:
    """Shared helpers in BaseLangSmithSpanProcessor."""

    def _base(self, **kwargs) -> BaseLangSmithSpanProcessor:
        return BaseLangSmithSpanProcessor(downstream_processor=MagicMock(), **kwargs)

    def test_set_messages_writes_json_messages_form(self):
        # One form for everything: the singular {"messages": [...]} JSON, and NOT
        # the indexed gen_ai.prompt.{n}.* attributes (which win at ingest and can
        # only express plain role/string-content).
        ls = TranslatedSpan.of(_make_span("x"))
        ls.set_messages(prompt=[{"role": "user", "content": "hi"}])
        assert json.loads(ls.attributes["gen_ai.prompt"]) == {
            "messages": [{"role": "user", "content": "hi"}]
        }
        assert "gen_ai.prompt.0.role" not in ls.attributes

    def test_set_messages_preserves_structured_fields(self):
        # tool_calls survive verbatim in the {"messages": [...]} form.
        ls = TranslatedSpan.of(_make_span("x"))
        tool_call = {"id": "c1", "function": {"name": "f", "arguments": "{}"}}
        ls.set_messages(
            completion=[{"role": "assistant", "content": "", "tool_calls": [tool_call]}]
        )
        payload = json.loads(ls.attributes["gen_ai.completion"])
        assert payload["messages"][0]["tool_calls"] == [tool_call]
        assert "gen_ai.completion.0.role" not in ls.attributes

    def test_attach_audio_encodes_and_returns_true(self):
        base = self._base()
        ls = TranslatedSpan.of(_make_span("x"))
        ok = base._attach_audio(
            ls, name="a.wav", data=b"RIFFdata", mime_type="audio/wav"
        )
        assert ok is True
        payload = json.loads(ls.attributes["langsmith.attachments"])
        assert base64.b64decode(payload[0]["content"]) == b"RIFFdata"

    def test_attach_audio_skips_oversize(self):
        base = self._base(audio_size_limit_bytes=4)
        ls = TranslatedSpan.of(_make_span("x"))
        ok = base._attach_audio(
            ls, name="a.wav", data=b"toolarge", mime_type="audio/wav"
        )
        assert ok is False
        assert "langsmith.attachments" not in ls.attributes

    def test_attach_audio_empty_returns_false(self):
        base = self._base()
        ls = TranslatedSpan.of(_make_span("x"))
        assert (
            base._attach_audio(ls, name="a.wav", data=b"", mime_type="audio/wav")
            is False
        )

    def test_stamp_static_metadata(self):
        # Static metadata lands on the draft; None values are skipped.
        base = self._base(metadata={"env": "test", "skip": None})
        tspan = TranslatedSpan.of(_make_span("x"))
        base._stamp_static_metadata(tspan)
        assert tspan.attributes["langsmith.metadata.env"] == "test"
        assert "langsmith.metadata.skip" not in tspan.attributes

    def test_stamp_static_metadata_never_clobbers(self):
        # An attribute already on the span wins over the static default.
        base = self._base(metadata={"env": "static"})
        tspan = TranslatedSpan.of(
            _make_span("x", {"langsmith.metadata.env": "explicit"})
        )
        base._stamp_static_metadata(tspan)
        assert tspan.attributes["langsmith.metadata.env"] == "explicit"

    def test_on_start_delegates_downstream(self):
        base = self._base()
        base.on_start(MagicMock())
        base.downstream.on_start.assert_called_once()

    def test_shutdown_delegates(self):
        base = self._base()
        base.shutdown()
        base.downstream.shutdown.assert_called_once()

    def test_force_flush_delegates(self):
        base = self._base()
        base.downstream.force_flush.return_value = True
        assert base.force_flush(5000) is True
        base.downstream.force_flush.assert_called_once_with(5000)

    def test_default_audio_size_limit_constant(self):
        base = self._base()
        assert base.audio_size_limit_bytes == DEFAULT_AUDIO_SIZE_LIMIT


class TestVoiceAudioUtils:
    """``pcm_to_wav`` — the only ``voice/audio.py`` helper Pipecat uses.

    The Track-B helpers (``scrub``/``dump_event``/``build_stereo_session_wav``)
    live with ``session.py`` in the OpenAI Realtime PR and are tested there.
    """

    def test_pcm_to_wav_empty(self):
        assert audio_utils.pcm_to_wav(b"", 16000) == b""

    def test_pcm_to_wav_produces_valid_wav(self):
        pcm = b"\x00\x01" * 16
        wav = audio_utils.pcm_to_wav(pcm, 16000, num_channels=2)
        assert wav[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav), "rb") as wf:
            assert wf.getnchannels() == 2
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2

    def test_stereo_session_wav_duration_cap_bounds_frames(self):
        wav = audio_utils.build_stereo_session_wav(
            [(0.0, b"\x01\x02" * 20), (60.0, b"\x03\x04" * 20)],
            [],
            10,
            max_duration_seconds=1.0,
        )
        with wave.open(io.BytesIO(wav), "rb") as wf:
            assert wf.getnframes() == 10


class TestStateLifecycle:
    """TTL-bounded state and its normal cleanup."""

    def test_state_cleaned_up_on_conversation_end(self):
        proc = _processor()
        trace_id = 0xABC
        llm = _make_span(
            "llm",
            {"input": json.dumps([{"role": "user", "content": "hi"}]), "output": "ok"},
            trace_id=trace_id,
        )
        proc.on_end(llm)
        proc._accumulate_audio("c1", b"\x00\x01\x02\x03" * 8, 16000, 2)
        assert len(proc._transcript_by_trace) == 1
        assert len(proc._audio_by_conversation) == 1

        convo = _make_span("conversation", {"conversation.id": "c1"}, trace_id=trace_id)
        proc.on_end(convo)

        # Both per-conversation stores are freed once the root renders.
        assert len(proc._transcript_by_trace) == 0
        assert len(proc._audio_by_conversation) == 0

    def test_abandoned_state_expires_via_ttl(self):
        # A conversation whose end span never arrives must not leak: the TTL
        # store drops it. Use a zero TTL so the next write evicts it.
        proc = _processor(state_ttl_seconds=0)
        proc._accumulate_audio("c1", b"\x00\x01\x02\x03", 16000, 2)
        # A later write to the (separate) store of a *different* conversation
        # triggers eviction of the expired one.
        proc._accumulate_audio("c2", b"\x00\x01\x02\x03", 16000, 2)

        assert "c1" not in proc._audio_by_conversation

    def test_active_call_not_evicted_mid_stream(self):
        # Re-writing a key (each audio chunk) refreshes its TTL, so a long call
        # streaming audio is never dropped mid-conversation.
        proc = _processor(state_ttl_seconds=60)
        proc._accumulate_audio("c1", b"\x00\x01\x02\x03", 16000, 2)
        proc._accumulate_audio("c1", b"\x04\x05\x06\x07", 16000, 2)
        assert (
            bytes(proc._audio_by_conversation["c1"].pcm)
            == b"\x00\x01\x02\x03\x04\x05\x06\x07"
        )


class TestExceptionIsolation:
    """A translation failure must never drop a span or escape on_end."""

    def test_dispatch_failure_still_exports_and_does_not_raise(self):
        proc = _processor()
        span = _make_span("conversation", {"conversation.id": "c1"})

        # Force the handler to blow up after classification.
        with patch.object(
            proc, "_handle_conversation", side_effect=RuntimeError("boom")
        ):
            proc.on_end(span)  # must not raise

        # The span is still forwarded downstream (untranslated, not lost).
        proc.downstream.on_end.assert_called_once()

    def test_export_failure_is_swallowed(self):
        proc = _processor()
        proc.downstream.on_end.side_effect = RuntimeError("export down")
        span = _make_span("stt", {"transcript": "hi"})

        proc.on_end(span)  # must not raise


class TestContextVarThreadId:
    """Thread-id injection from the per-context ``set_thread_id`` ContextVar."""

    def teardown_method(self):
        set_thread_id(None)

    def test_set_thread_id_is_injected(self):
        proc = _processor()
        set_thread_id("conv-42")
        proc.on_start(_make_span("turn", {}))
        proc.on_end(_make_span("turn", {}))

        assert _exported_attrs(proc)["langsmith.metadata.thread_id"] == "conv-42"

    def test_no_injection_when_unset(self):
        proc = _processor()
        assert thread_id_from_context() is None
        span = _make_span("turn", {})

        proc.on_end(span)

        assert "langsmith.metadata.thread_id" not in _exported_attrs(proc)

    def test_does_not_clobber_upstream_id(self):
        proc = _processor()
        set_thread_id("from-context")
        span = _make_span("turn", {"langsmith.metadata.thread_id": "upstream"})

        proc.on_end(span)

        assert _exported_attrs(proc)["langsmith.metadata.thread_id"] == "upstream"

    def test_thread_id_survives_out_of_context_end(self):
        # The real failure mode: a span that ENDS in a detached task can't see
        # the ContextVar. on_start captured it (in context) keyed by trace, so
        # the span still gets the id at export. Simulate the detached end by
        # clearing the ContextVar between on_start and on_end.
        proc = _processor()
        tid = 0xABC
        set_thread_id("conv-7")
        proc.on_start(_make_span("conversation", trace_id=tid))
        set_thread_id(None)
        proc.on_end(_make_span("stt", {"transcript": "hi"}, trace_id=tid))

        assert _exported_attrs(proc)["langsmith.metadata.thread_id"] == "conv-7"

    def test_cleanup_forgets_cached_thread_id(self):
        proc = _processor()
        tid = 0xABC
        set_thread_id("conv-9")
        proc.on_start(_make_span("turn", {}, trace_id=tid))
        assert tid in proc._thread_id_by_trace
        # Conversation end frees the per-trace state, the thread id included.
        proc.on_end(_make_span("conversation", {"conversation.id": "c1"}, trace_id=tid))
        assert tid not in proc._thread_id_by_trace


class TestDispatchExportDisposition:
    """``_dispatch``'s return value decides whether the base exports the span.

    This is the contract a deferring subclass (e.g. LiveKit's egress
    hold-the-root-open) relies on: return ``False`` to own/defer the export.
    """

    def _proc(self, dispatch_returns):
        class _P(BaseLangSmithSpanProcessor):
            def _dispatch(self, tspan):
                return dispatch_returns

        return _P(downstream_processor=MagicMock())

    def test_true_exports_once(self):
        proc = self._proc(True)
        span = _make_span("x")
        proc.on_end(span)
        proc.downstream.on_end.assert_called_once()

    def test_false_defers_export(self):
        # The subclass takes ownership; the base must NOT export it.
        proc = self._proc(False)
        span = _make_span("x")
        proc.on_end(span)
        proc.downstream.on_end.assert_not_called()

    def test_none_still_exports(self):
        # A subclass that forgets to return must not silently drop the span.
        proc = self._proc(None)
        span = _make_span("x")
        proc.on_end(span)
        proc.downstream.on_end.assert_called_once()


class TestConfigureAndWarning:
    """Public surface: the beta warning and configure_pipecat."""

    def test_configure_pipecat_emits_beta_warning(self):
        from langsmith.integrations.pipecat import configure_pipecat

        _warn_once.cache_clear()  # @warn_beta dedupes per message; reset it
        # @warn_beta fires before the body, so it warns even when pipecat is
        # absent (the call then returns None).
        with patch.dict(sys.modules, {"pipecat": None}):
            with pytest.warns(LangSmithBetaWarning):
                assert configure_pipecat() is None

    def test_configure_pipecat_returns_none_without_pipecat(self):
        from langsmith.integrations.pipecat import configure_pipecat

        # Force the lazy ``import pipecat`` to fail regardless of environment.
        with patch.dict(sys.modules, {"pipecat": None}):
            assert configure_pipecat() is None


class TestPipecatUsageCapture:
    """Token/usage capture for cost: LLM usage + detail, realtime spans."""

    def test_llm_usage_and_detail_lifted(self):
        proc = _processor()
        span = _make_span(
            "llm",
            {
                "input": json.dumps([{"role": "user", "content": "hi"}]),
                "output": "hello",
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 50,
                "gen_ai.usage.cache_read.input_tokens": 20,
                "gen_ai.usage.reasoning_tokens": 8,
            },
        )
        proc.on_end(span)
        usage = json.loads(_exported_attrs(proc)["langsmith.usage_metadata"])
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["input_token_details"] == {"cache_read": 20}
        assert usage["output_token_details"] == {"reasoning": 8}

    def test_realtime_llm_response_priced_and_transcribed(self):
        # Speech-to-speech services emit `llm_response` (not `llm`); it carries
        # aggregate usage (Pipecat drops the audio split) and the reply.
        proc = _processor()
        trace_id = 0x55
        span = _make_span(
            "llm_response",
            {
                "text_output": "the weather is sunny",
                "gen_ai.usage.input_tokens": 300,
                "gen_ai.usage.output_tokens": 120,
            },
            trace_id=trace_id,
        )
        proc.on_end(span)
        attrs = _exported_attrs(proc)
        assert attrs["langsmith.span.kind"] == "llm"
        usage = json.loads(attrs["langsmith.usage_metadata"])
        assert usage["input_tokens"] == 300
        assert usage["output_tokens"] == 120
        completion = json.loads(attrs["gen_ai.completion"])["messages"]
        assert completion[0]["content"] == "the weather is sunny"
        # Reply folds into the conversation the root renders.
        assert (
            proc._transcript_by_trace[trace_id][-1]["content"] == "the weather is sunny"
        )

    def test_realtime_rollup_has_user_and_agent_turns(self):
        # Realtime has no cascade `llm` span carrying history: the user turn
        # arrives on a standard `stt` span, the agent reply on `llm_response`.
        # Both must fold into the conversation rollup the root renders.
        proc = _processor()
        trace_id = 0x56
        proc.on_end(_make_span("stt", {"transcript": "what's the weather?"}, trace_id))
        proc.on_end(
            _make_span("llm_response", {"output": "it's sunny"}, trace_id=trace_id)
        )
        rollup = proc._transcript_by_trace[trace_id]
        assert [(m["role"], m["content"]) for m in rollup] == [
            ("user", "what's the weather?"),
            ("assistant", "it's sunny"),
        ]

    def test_stt_interim_transcript_not_folded(self):
        # Non-final STT results must not pollute the rollup with partials.
        proc = _processor()
        trace_id = 0x57
        proc.on_end(
            _make_span("stt", {"transcript": "what's", "is_final": False}, trace_id)
        )
        assert trace_id not in proc._transcript_by_trace

    def test_realtime_wrapper_spans_are_chain(self):
        proc = _processor()
        for name in ("llm_setup", "llm_request"):
            proc.on_end(_make_span(name, {}))
            assert _exported_attrs(proc)["langsmith.span.kind"] == "chain"
