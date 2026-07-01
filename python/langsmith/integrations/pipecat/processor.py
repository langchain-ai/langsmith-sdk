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
import logging
from collections.abc import MutableMapping
from typing import Any, Optional

from cachetools import TTLCache

from langsmith._internal.voice.audio import pcm_to_wav
from langsmith._internal.voice.base_span_processor import (
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)

logger = logging.getLogger(__name__)

# Default lifetime (seconds) for the per-conversation state held between a
# trace's first and last span. The normal path frees it when the conversation
# span ends; the TTL bounds it for conversations that never emit that span
# (crash, cancelled task, dropped connection).
DEFAULT_STATE_TTL_SECONDS = 3600.0

# Hard ceiling on tracked conversations, independent of the TTL — a backstop
# against a flood of new conversations within one TTL window (oldest evicted
# first). The TTL is the governing limit in practice.
DEFAULT_STATE_MAXSIZE = 100_000


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
        audio_mime_type: str = "audio/wav",
        state_ttl_seconds: float = DEFAULT_STATE_TTL_SECONDS,
        **kwargs: Any,
    ) -> None:
        """Create the processor.

        Args:
            downstream_processor: where rewritten spans are forwarded; defaults
                to a LangSmith OTLP exporter (see the base class).
            llm_span_kind: LangSmith run kind for Pipecat's ``llm`` span (see the
                module docstring).
            audio_mime_type: MIME type for the attached conversation recording.
            state_ttl_seconds: lifetime for the per-conversation state held
                between a trace's first and last span; the backstop that frees
                state for conversations that never emit their end span.
        """
        super().__init__(
            downstream_processor,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
            **kwargs,
        )
        self._llm_span_kind = llm_span_kind
        self._audio_mime_type = audio_mime_type
        # NB: ``TTLCache`` is not thread-safe. Both caches are mutated only from
        # the single Pipecat asyncio event loop (``on_end`` and
        # ``_accumulate_audio`` both run there); ending spans off that loop would
        # need external synchronization.
        # The latest llm request's full context per trace — each request carries
        # the whole history, so the last snapshot IS the conversation. Rendered
        # onto the root ``conversation`` span, which ends last. TTL-bounded so an
        # abandoned conversation (no end span) can't leak it.
        self._conversation_by_trace: MutableMapping[str, list] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )
        # Merged PCM accumulated from a Pipecat AudioBufferProcessor (see
        # attach_audio_buffer), keyed by conversation id. Each value is
        # {"pcm": bytearray, "sample_rate": int, "num_channels": int}. Also
        # TTL-bounded — these entries hold the raw audio and are the larger leak.
        self._audio_by_conversation: MutableMapping[str, dict[str, Any]] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )

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
        rec["pcm"].extend(audio)
        rec["sample_rate"] = sample_rate
        rec["num_channels"] = num_channels
        # Re-assign (not just mutate) so the TTL timestamp is refreshed — an
        # active call streaming audio for longer than the TTL must not be
        # evicted mid-conversation.
        self._audio_by_conversation[conversation_id] = rec

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        trace_id = format(tspan.span.context.trace_id, "032x")
        name = tspan.span.name

        if name == "stt":
            self._handle_stt(tspan)
            self._exclude_from_message_view(tspan)
        elif name == "llm":
            self._handle_llm(tspan, trace_id)
        elif name == "tts":
            self._handle_tts(tspan)
            self._exclude_from_message_view(tspan)
        elif name == "turn":
            self._handle_turn(tspan)
        elif name == "conversation":
            self._handle_conversation(tspan, trace_id)
        # Any other span (e.g. nested LangChain/LangGraph runs riding the same
        # OTel provider) already arrives in LangSmith's native shape, so it's
        # exported untouched.
        #
        # Pipecat's ``conversation`` span genuinely ends last, so nothing is
        # deferred: return True to have the base export every span once.
        return True

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, tspan: TranslatedSpan) -> None:
        """STT span: audio input → transcribed text."""
        transcript = tspan.attributes.get("transcript", "")
        self._set_kind(tspan, "llm")
        self._set_messages(
            tspan, prompt=[{"role": "user", "content": f'Audio for: "{transcript}"'}]
        )
        if transcript:
            self._set_messages(
                tspan, completion=[{"role": "assistant", "content": str(transcript)}]
            )

    @classmethod
    def _completion_message(cls, output_data: Any) -> dict:
        """Build the assistant completion message for the ``llm`` span.

        Pipecat's ``output`` attribute is normally the assistant's text. But if a
        service emits the structured response instead (a dict carrying
        ``tool_calls``), forward it unchanged in its OpenAI shape so LangSmith
        renders the tool calls rather than flattening them to a string. Anything
        else — plain text, or JSON that isn't a tool-call message — stays as text
        content, preserving the existing behavior.
        """
        parsed: Any = output_data
        if isinstance(output_data, str):
            try:
                parsed = json.loads(output_data)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, dict) and parsed.get("tool_calls"):
            return {"role": "assistant", **parsed}
        content = output_data if isinstance(output_data, str) else str(output_data)
        return {"role": "assistant", "content": content}

    def _handle_llm(self, tspan: TranslatedSpan, trace_id: str) -> None:
        """Framework ``llm`` span: the LLM stage of the pipeline.

        Pipecat logs the request history in the LLM provider's own message format
        (via the service's logging adapter). We forward it unchanged — LangSmith
        reads the messages directly from ``gen_ai.prompt`` — so the trace mirrors
        exactly what the model was sent.
        """
        input_data = tspan.attributes.get("input", "")
        output_data = tspan.attributes.get("output", "")
        self._set_kind(tspan, self._llm_span_kind)

        try:
            raw_messages = json.loads(input_data)
        except (json.JSONDecodeError, TypeError):
            raw_messages = []
        messages = [
            m
            for m in (raw_messages if isinstance(raw_messages, list) else [])
            if isinstance(m, dict)
        ]

        if messages:
            self._set_messages_json(tspan, prompt=messages)
        if output_data:
            self._set_messages_json(
                tspan, completion=[self._completion_message(output_data)]
            )

        # Each request's input carries the full history, so the latest snapshot
        # IS the conversation — kept per trace for the root span to render. Reuse
        # _completion_message so the root transcript and this span's completion
        # render the assistant turn identically (tool calls included).
        transcript = [m for m in messages if m.get("role") != "system"]
        if output_data:
            transcript.append(self._completion_message(output_data))
        if transcript:
            self._conversation_by_trace[trace_id] = transcript

    def _handle_tts(self, tspan: TranslatedSpan) -> None:
        """TTS span: text → audio. The voice is metadata, not content."""
        text = tspan.attributes.get("text", "")
        self._set_kind(tspan, "llm")
        voice_id = tspan.attributes.get("voice_id")
        if voice_id:
            tspan.attributes["langsmith.metadata.voice_id"] = str(voice_id)
        self._set_messages(
            tspan,
            prompt=[{"role": "user", "content": str(text)}],
            completion=[
                {"role": "assistant", "content": f'Generated audio for: "{text}"'}
            ],
        )

    def _handle_turn(self, tspan: TranslatedSpan) -> None:
        """Turn span: a framework wrapper around one exchange (a ``chain``)."""
        self._set_kind(tspan, "chain")
        turn_number = tspan.attributes.get("turn.number")
        if turn_number is not None:
            tspan.attributes["langsmith.metadata.turn_number"] = turn_number
        was_interrupted = tspan.attributes.get("turn.was_interrupted")
        if was_interrupted is not None:
            tspan.attributes["langsmith.metadata.turn_was_interrupted"] = (
                was_interrupted
            )

    def _handle_conversation(self, tspan: TranslatedSpan, trace_id: str) -> None:
        """Conversation span: the whole session; the LangSmith root.

        Input = the opening message; output = everything after it. Pipecat's
        conversation span genuinely ends last, so no deferral is needed.
        """
        conversation_id = tspan.attributes.get(
            "conversation.id", ""
        ) or tspan.attributes.get("conversation_id", "")
        self._set_kind(tspan, "chain")
        tspan.attributes["langsmith.root_span"] = True
        tspan.attributes["langsmith.metadata.ls_modality"] = "audio"

        messages = self._conversation_by_trace.get(trace_id, [])
        if messages:
            self._set_messages_json(tspan, prompt=messages[:1])
            if len(messages) > 1:
                self._set_messages_json(tspan, completion=messages[1:])

        self._attach_conversation_audio(tspan, conversation_id)
        self._cleanup_conversation(trace_id, conversation_id)

    # -- audio attachment -----------------------------------------------------

    def _attach_conversation_audio(
        self, tspan: TranslatedSpan, conversation_id: Any
    ) -> None:
        """Encode the accumulated PCM (from the AudioBufferProcessor) and attach it.

        Looked up strictly by ``conversation_id`` — never by "the only recording
        in flight": a heuristic match could attach a different caller's audio to
        this trace (a privacy leak on a multi-tenant server). The id passed to
        :meth:`attach_audio_buffer` must match the ``PipelineTask``
        ``conversation_id``; a mismatch attaches nothing (logged below).
        """
        rec = self._audio_by_conversation.get(conversation_id)
        if rec is None:
            if len(self._audio_by_conversation) > 0:
                logger.debug(
                    "langsmith voice: no recording for conversation_id=%r "
                    "(%d recording(s) in flight under other ids); audio not "
                    "attached. Ensure the id passed to attach_audio_buffer "
                    "matches the PipelineTask conversation_id.",
                    conversation_id,
                    len(self._audio_by_conversation),
                )
            return
        if not rec["pcm"]:
            return
        wav = pcm_to_wav(bytes(rec["pcm"]), rec["sample_rate"], rec["num_channels"])
        self._attach_audio(
            tspan, name="conversation.wav", data=wav, mime_type=self._audio_mime_type
        )

    def _cleanup_conversation(self, trace_id: str, conversation_id: Any) -> None:
        self._conversation_by_trace.pop(trace_id, None)
        self._audio_by_conversation.pop(conversation_id, None)
        self._forget_thread_id(int(trace_id, 16))
