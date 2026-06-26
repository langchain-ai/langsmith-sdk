"""OTel → LangSmith bridge for Pipecat.

Pipecat emits OTel spans named ``conversation``, ``turn``, ``stt``, ``llm``, and
``tts`` with attributes (``transcript``, ``input``/``output``, ``text``,
``turn.number``, …) that LangSmith's OTLP ingester doesn't recognize. This
:class:`PipecatLangSmithSpanProcessor` rewrites each span type into the
``gen_ai.*`` / ``langsmith.*`` namespaces LangSmith keys off, renders the whole
conversation onto the root span, and (optionally) attaches the recorded audio
there. It inherits the downstream wrapping, exporter, ``thread_id`` injection,
and message helpers from :class:`BaseLangSmithSpanProcessor`.

Trace shape in LangSmith::

    conversation                      (root; whole transcript + conversation WAV)
    └── turn × N                      (per exchange; carries was_interrupted)
        ├── stt                       (audio → transcript)
        ├── llm                       (the LLM stage; kind set by llm_span_kind)
        └── tts                       (response text → audio)

Audio recording uses Pipecat's own
:class:`~pipecat.processors.audio.audio_buffer_processor.AudioBufferProcessor`:
call :meth:`attach_audio_buffer` to wire its ``on_audio_data`` event, and the
processor accumulates the merged PCM and attaches it (as a WAV) to the root span
when the conversation ends. Place the ``AudioBufferProcessor`` *after*
``transport.output()`` so it captures the bot audio as actually played
(post-barge-in-truncation) plus the user audio.

``llm_span_kind`` controls the kind of the span Pipecat names ``llm``. Keep the
default ``"llm"`` when that stage does its own inference (stock services such as
``OpenAILLMService``). Pass ``"chain"`` when it only orchestrates nested runs
that are exported to LangSmith themselves (an in-process LangGraph/LangChain
brain): the nested ``model`` runs are then the real ``llm`` inference, and
tagging the wrapper ``llm`` too would double-count the conversation in the
Messages view. This can't be auto-detected at span-end time (the nested runs are
exported later, from a background queue), so the caller states it explicitly.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from opentelemetry.sdk.trace import ReadableSpan

from .._voice.audio import pcm_to_wav
from .._voice.base import BaseLangSmithSpanProcessor


class PipecatLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches Pipecat's OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[Any] = None,
        *,
        llm_span_kind: str = "llm",
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
        audio_mime_type: str = "audio/wav",
        **kwargs: Any,
    ) -> None:
        """Create the processor.

        Args:
            downstream_processor: where rewritten spans are forwarded; defaults
                to a LangSmith OTLP exporter (see the base class).
            llm_span_kind: LangSmith run kind for Pipecat's ``llm`` span (see the
                module docstring).
            audio_mime_type: MIME type for the attached conversation recording.
            thread_id_provider: opt-in conversation id for LangSmith thread
                grouping; ``None`` disables.
        """
        super().__init__(
            downstream_processor,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
            thread_id_provider=thread_id_provider,
            **kwargs,
        )
        self._llm_span_kind = llm_span_kind
        self._audio_mime_type = audio_mime_type
        # The latest llm request's full context per trace — each request carries
        # the whole history, so the last snapshot IS the conversation. Rendered
        # onto the root ``conversation`` span, which ends last.
        self._conversation_by_trace: dict[str, list] = {}
        # Merged PCM accumulated from a Pipecat AudioBufferProcessor (see
        # attach_audio_buffer), keyed by conversation id. Each value is
        # {"pcm": bytearray, "sample_rate": int, "num_channels": int}.
        self._audio_by_conversation: dict[str, dict[str, Any]] = {}

    # -- audio buffer registration -------------------------------------------

    def attach_audio_buffer(self, audio_buffer: Any, conversation_id: str) -> None:
        """Record this conversation's audio from a Pipecat ``AudioBufferProcessor``.

        Registers an ``on_audio_data`` handler on ``audio_buffer`` that
        accumulates the merged PCM for ``conversation_id``; it's encoded to a WAV
        and attached to the root span when the ``conversation`` span ends. The
        ``conversation_id`` must match the one set on ``PipelineTask`` (so it
        appears on the ``conversation`` span).

        Place the ``AudioBufferProcessor`` after ``transport.output()`` and start
        it with ``await audio_buffer.start_recording()`` once the session is
        running. Construct it with a non-zero ``buffer_size`` so audio streams in
        periodically — with the default single-shot emission, the final chunk can
        arrive after the conversation span has already been exported.
        """

        async def _on_audio_data(
            buffer: Any, audio: bytes, sample_rate: int, num_channels: int
        ) -> None:
            self._accumulate_audio(conversation_id, audio, sample_rate, num_channels)

        audio_buffer.event_handler("on_audio_data")(_on_audio_data)

    def _accumulate_audio(
        self, conversation_id: str, audio: bytes, sample_rate: int, num_channels: int
    ) -> None:
        rec = self._audio_by_conversation.get(conversation_id)
        if rec is None:
            rec = {
                "pcm": bytearray(),
                "sample_rate": sample_rate,
                "num_channels": num_channels,
            }
            self._audio_by_conversation[conversation_id] = rec
        rec["pcm"].extend(audio)
        rec["sample_rate"] = sample_rate
        rec["num_channels"] = num_channels

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, span: ReadableSpan) -> None:
        trace_id = format(span.context.trace_id, "032x")
        name = span.name

        if name == "stt":
            self._handle_stt(span)
            self._exclude_from_message_view(span)
        elif name == "llm":
            self._handle_llm(span, trace_id)
        elif name == "tts":
            self._handle_tts(span)
            self._exclude_from_message_view(span)
        elif name == "turn":
            self._handle_turn(span)
        elif name == "conversation":
            self._handle_conversation(span, trace_id)
        # Any other span (e.g. nested LangChain/LangGraph runs riding the same
        # OTel provider) already arrives in LangSmith's native shape, so it's
        # exported untouched.

        self._export(span)

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, span: ReadableSpan) -> None:
        """STT span: audio input → transcribed text."""
        transcript = span.attributes.get("transcript", "")
        self._set_kind(span, "llm")
        self._set_messages(
            span, prompt=[{"role": "user", "content": f'Audio for: "{transcript}"'}]
        )
        if transcript:
            self._set_messages(
                span, completion=[{"role": "assistant", "content": str(transcript)}]
            )

    def _handle_llm(self, span: ReadableSpan, trace_id: str) -> None:
        """Framework ``llm`` span: the LLM stage of the pipeline."""
        input_data = span.attributes.get("input", "")
        output_data = span.attributes.get("output", "")
        self._set_kind(span, self._llm_span_kind)

        try:
            raw_messages = json.loads(input_data)
        except (json.JSONDecodeError, TypeError):
            raw_messages = []
        messages = [
            self._to_langchain_message(m)
            for m in (raw_messages if isinstance(raw_messages, list) else [])
            if isinstance(m, dict)
        ]

        if messages:
            self._set_messages_json(span, prompt=messages)
        if output_data:
            self._set_messages_json(
                span, completion=[{"role": "assistant", "content": output_data}]
            )

        # Each request's input carries the full history, so the latest snapshot
        # IS the conversation — kept per trace for the root span to render.
        transcript = [m for m in messages if m.get("role") != "system"]
        if output_data:
            transcript.append({"role": "assistant", "content": output_data})
        if transcript:
            self._conversation_by_trace[trace_id] = transcript

    def _handle_tts(self, span: ReadableSpan) -> None:
        """TTS span: text → audio. The voice is metadata, not content."""
        text = span.attributes.get("text", "")
        self._set_kind(span, "llm")
        voice_id = span.attributes.get("voice_id")
        if voice_id:
            span._attributes["langsmith.metadata.voice_id"] = str(voice_id)
        self._set_messages(
            span,
            prompt=[{"role": "user", "content": str(text)}],
            completion=[
                {"role": "assistant", "content": f'Generated audio for: "{text}"'}
            ],
        )

    def _handle_turn(self, span: ReadableSpan) -> None:
        """Turn span: a framework wrapper around one exchange (a ``chain``)."""
        self._set_kind(span, "chain")
        turn_number = span.attributes.get("turn.number")
        if turn_number is not None:
            span._attributes["langsmith.metadata.turn_number"] = turn_number
        was_interrupted = span.attributes.get("turn.was_interrupted")
        if was_interrupted is not None:
            span._attributes["langsmith.metadata.turn_was_interrupted"] = (
                was_interrupted
            )

    def _handle_conversation(self, span: ReadableSpan, trace_id: str) -> None:
        """Conversation span: the whole session; the LangSmith root.

        Input = the opening message; output = everything after it. Pipecat's
        conversation span genuinely ends last, so no deferral is needed.
        """
        conversation_id = span.attributes.get(
            "conversation.id", ""
        ) or span.attributes.get("conversation_id", "")
        self._set_kind(span, "chain")
        span._attributes["langsmith.root_span"] = True
        span._attributes["langsmith.metadata.ls_modality"] = "audio"

        messages = self._conversation_by_trace.get(trace_id, [])
        if messages:
            self._set_messages_json(span, prompt=messages[:1])
            if len(messages) > 1:
                self._set_messages_json(span, completion=messages[1:])

        self._attach_conversation_audio(span, conversation_id)
        self._cleanup_conversation(trace_id, conversation_id)

    # -- audio attachment -----------------------------------------------------

    def _attach_conversation_audio(
        self, span: ReadableSpan, conversation_id: Any
    ) -> None:
        """Encode the accumulated PCM (from the AudioBufferProcessor) and attach it."""
        rec = self._audio_by_conversation.get(conversation_id)
        if rec is None and len(self._audio_by_conversation) == 1:
            rec = next(iter(self._audio_by_conversation.values()))
        if not rec or not rec["pcm"]:
            return
        wav = pcm_to_wav(bytes(rec["pcm"]), rec["sample_rate"], rec["num_channels"])
        self._attach_audio(
            span, name="conversation.wav", data=wav, mime_type=self._audio_mime_type
        )

    def _cleanup_conversation(self, trace_id: str, conversation_id: Any) -> None:
        self._conversation_by_trace.pop(trace_id, None)
        self._audio_by_conversation.pop(conversation_id, None)
