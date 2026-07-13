"""OTel → LangSmith bridge for Pipecat.

Rewrites Pipecat's ``conversation`` / ``turn`` / ``stt`` / ``llm`` / ``tts`` OTel
spans into the ``gen_ai.*`` / ``langsmith.*`` namespaces LangSmith ingests, rolls
the whole conversation onto the root ``conversation`` span, and optionally
attaches the recorded audio there; non-Pipecat spans pass through untouched.
Shared export / ``thread_id`` / message plumbing lives in
:class:`BaseLangSmithSpanProcessor`.

Trace shape::

    conversation                 (root; whole transcript + conversation WAV)
    └── turn × N
        ├── stt                  (audio → transcript)
        ├── llm                  (the LLM stage; kind set by llm_span_kind)
        └── tts                  (response text → audio)

Audio uses Pipecat's ``AudioBufferProcessor``: wire it with
:meth:`attach_audio_buffer` (placed after ``transport.output()``, constructed
with ``num_channels=2``); the merged stereo (user-left / bot-right) it emits is
attached as a WAV when the conversation ends.

``llm_span_kind`` sets the kind for Pipecat's ``llm`` span — keep ``"llm"`` for a
service that does its own inference; pass ``"chain"`` when it only orchestrates
nested runs exported separately (else the conversation double-counts).

Speech-to-speech (realtime) services emit operation-named spans: ``llm_response``
(→ ``llm`` run, usage + reply) and the ``llm_setup`` / ``llm_request`` wrappers.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from cachetools import TTLCache
from opentelemetry.sdk.trace import SpanProcessor

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice._helpers import (
    build_assistant_message,
    build_user_message,
)
from langsmith._internal.voice.audio import pcm_to_wav
from langsmith._internal.voice.base_span_processor import (
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)
from langsmith.integrations.pipecat._helpers import (
    build_completion_message,
    extract_llm_usage,
    parse_llm_messages,
)

if TYPE_CHECKING:
    from pipecat.processors.audio.audio_buffer_processor import (  # type: ignore[import-not-found]
        AudioBufferProcessor,
    )

logger = logging.getLogger(__name__)

# Lifetime / cap for per-conversation state; bounds memory for calls that never end.
DEFAULT_STATE_TTL_SECONDS = 3600.0
DEFAULT_STATE_MAXSIZE = 100_000

_WAV_HEADER_BYTES = 44


@dataclass
class _AudioRecord:
    """Merged PCM accumulated for one conversation, plus its WAV parameters.

    Pipecat's ``AudioBufferProcessor`` emits already-merged audio — stereo
    (user-left / bot-right) when constructed with ``num_channels=2`` — so we just
    accumulate and wrap it.
    """

    sample_rate: int
    num_channels: int
    pcm: bytearray = field(default_factory=bytearray)
    audio_truncated: bool = False

    def extend(
        self,
        audio: bytes,
        sample_rate: int,
        num_channels: int,
        limit_bytes: Optional[int],
    ) -> None:
        """Append PCM (truncating at ``limit_bytes``) and refresh the WAV params."""
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        if limit_bytes is not None:
            remaining = limit_bytes - len(self.pcm)
            remaining -= remaining % (2 * num_channels)  # keep whole frames
            if remaining <= 0:
                self.audio_truncated = True
                return
            if len(audio) > remaining:
                self.audio_truncated = True
                audio = audio[:remaining]
        self.pcm.extend(audio)


class PipecatLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches Pipecat's OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[SpanProcessor] = None,
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
            llm_span_kind: LangSmith run kind for Pipecat's ``llm`` span.
            audio_mime_type: MIME type for the attached conversation recording.
            state_ttl_seconds: lifetime for per-conversation state.
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
        # trace_id -> latest llm context (the full history == the conversation),
        # rendered onto the root ``conversation`` span, which ends last.
        self._transcript_by_trace: MutableMapping[int, list[dict[str, Any]]] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )
        # conversation id -> merged PCM from an AudioBufferProcessor.
        self._audio_by_conversation: MutableMapping[str, _AudioRecord] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )

    # -- audio buffer registration -------------------------------------------

    def attach_audio_buffer(
        self, audio_buffer: AudioBufferProcessor, conversation_id: str
    ) -> None:
        """Record this conversation's audio from a Pipecat ``AudioBufferProcessor``.

        Registers an ``on_audio_data`` handler that accumulates the merged PCM
        Pipecat emits — construct the buffer with ``num_channels=2`` for a stereo
        (user-left / bot-right) recording that preserves barge-in overlap — and
        attaches it as a WAV when the ``conversation`` span ends.
        ``conversation_id`` must match the ``PipelineTask`` id. Place the buffer
        after ``transport.output()`` and give it a non-zero ``buffer_size`` so the
        final chunk arrives before the span is exported.
        """

        async def _on_audio_data(
            _buffer: AudioBufferProcessor,
            audio: bytes,
            sample_rate: int,
            num_channels: int,
        ) -> None:
            self._accumulate_audio(conversation_id, audio, sample_rate, num_channels)

        audio_buffer.event_handler("on_audio_data")(_on_audio_data)

    def _pcm_audio_size_limit_bytes(self) -> Optional[int]:
        if self.audio_size_limit_bytes is None:
            return None
        return max(0, self.audio_size_limit_bytes - _WAV_HEADER_BYTES)

    def _accumulate_audio(
        self,
        conversation_id: str,
        audio: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> None:
        rec = self._audio_by_conversation.get(conversation_id)
        if rec is None:
            if num_channels != 2:
                logger.warning(
                    "langsmith voice: AudioBufferProcessor num_channels=%d; use "
                    "num_channels=2 for a stereo (user-left/bot-right) recording "
                    "that preserves barge-in overlap.",
                    num_channels,
                )
            rec = _AudioRecord(sample_rate=sample_rate, num_channels=num_channels)
        rec.extend(audio, sample_rate, num_channels, self._pcm_audio_size_limit_bytes())
        # Re-assign (not just mutate) so each chunk refreshes the cache TTL.
        self._audio_by_conversation[conversation_id] = rec

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        trace_id = tspan.span.context.trace_id
        name = tspan.span.name

        if name == "stt":
            self._handle_stt(tspan, trace_id)
        elif name == "llm":
            self._handle_llm(tspan, trace_id)
        elif name == "tts":
            self._handle_tts(tspan)
        elif name == "turn":
            self._handle_turn(tspan)
        elif name == "conversation":
            self._handle_conversation(tspan, trace_id)
        elif name == "llm_response":  # realtime: usage + reply
            self._handle_realtime_response(tspan, trace_id)
        elif name in ("llm_setup", "llm_request"):
            tspan.set_kind("chain")  # realtime wrappers
        return True

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """STT span: audio input → transcribed text."""
        transcript = tspan.attributes.get("transcript", "")
        tspan.set_kind("llm")
        tspan.set_messages(prompt=[build_user_message(f'Audio for: "{transcript}"')])
        if transcript:
            tspan.set_messages(completion=[build_assistant_message(str(transcript))])
            # Fold the user turn into the rollup (realtime has no cascade llm
            # span to carry it; cascade's llm span replaces it with full history).
            if tspan.attributes.get("is_final", True):
                self._transcript_by_trace.setdefault(trace_id, []).append(
                    build_user_message(str(transcript))
                )
        tspan.exclude_from_message_view()

    def _handle_llm(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """``llm`` span: forward the request history and reply verbatim.

        Each request's ``input`` carries the whole history, so the latest snapshot
        is kept per trace as the conversation the root renders.
        """
        input_data = tspan.attributes.get("input", "")
        output_data = tspan.attributes.get("output", "")
        tspan.set_kind(self._llm_span_kind)

        messages = parse_llm_messages(input_data)
        if messages:
            tspan.set_messages(prompt=messages)
        if output_data:
            tspan.set_messages(completion=[build_completion_message(output_data)])

        usage = extract_llm_usage(tspan.attributes)
        if usage:
            tspan.set_usage(**usage)

        transcript = [m for m in messages if m.get("role") != "system"]
        if output_data:
            transcript.append(build_completion_message(output_data))
        if transcript:
            self._transcript_by_trace[trace_id] = transcript

    def _handle_tts(self, tspan: TranslatedSpan) -> None:
        """TTS span: text → audio. The voice is metadata, not content."""
        text = tspan.attributes.get("text", "")
        tspan.set_kind("llm")
        voice_id = tspan.attributes.get("voice_id")
        if voice_id:
            tspan.set_metadata("voice_id", str(voice_id))
        tspan.set_messages(
            prompt=[build_user_message(str(text))],
            completion=[build_assistant_message(f'Generated audio for: "{text}"')],
        )
        tspan.exclude_from_message_view()

    def _handle_realtime_response(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """``llm_response`` span from a realtime (speech-to-speech) service."""
        tspan.set_kind(self._llm_span_kind)
        output_data = tspan.attributes.get("output") or tspan.attributes.get(
            "text_output", ""
        )
        if output_data:
            completion = build_completion_message(output_data)
            tspan.set_messages(completion=[completion])
            self._transcript_by_trace.setdefault(trace_id, []).append(completion)

        usage = extract_llm_usage(tspan.attributes)
        if usage:
            tspan.set_usage(**usage)

    def _handle_turn(self, tspan: TranslatedSpan) -> None:
        """Turn span: a framework wrapper around one exchange (a ``chain``)."""
        tspan.set_kind("chain")
        turn_number = tspan.attributes.get("turn.number")
        if turn_number is not None:
            tspan.set_metadata("turn_number", turn_number)
        was_interrupted = tspan.attributes.get("turn.was_interrupted")
        if was_interrupted is not None:
            tspan.set_metadata("turn_was_interrupted", was_interrupted)

    def _handle_conversation(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """Conversation span: the whole session; the LangSmith root."""
        conversation_id = tspan.attributes.get(
            "conversation.id", ""
        ) or tspan.attributes.get("conversation_id", "")
        tspan.set_kind("chain")
        tspan.set_root_span(True)
        tspan.set_metadata("ls_modality", "audio")
        tspan.set_metadata("ls_integration", "pipecat")
        tspan.set_metadata(
            "ls_integration_version", get_package_version("pipecat-ai") or ""
        )

        messages = self._transcript_by_trace.get(trace_id, [])
        if messages:
            tspan.set_messages(prompt=messages)

        self._attach_conversation_audio(tspan, conversation_id)
        self._cleanup_conversation(trace_id, conversation_id)

    # -- audio attachment -----------------------------------------------------

    def _attach_conversation_audio(
        self, tspan: TranslatedSpan, conversation_id: str
    ) -> None:
        """Encode the accumulated PCM and attach it, keyed strictly by id.

        Never falls back to "the only recording in flight" — a heuristic match
        could attach another caller's audio to this trace (a privacy leak).
        """
        recording = self._audio_by_conversation.get(conversation_id)
        if recording is None:
            if len(self._audio_by_conversation) > 0:
                logger.debug(
                    "langsmith voice: no recording for conversation_id=%r "
                    "(%d in flight under other ids); audio not attached. Ensure "
                    "attach_audio_buffer's id matches the PipelineTask id.",
                    conversation_id,
                    len(self._audio_by_conversation),
                )
            return
        if not recording.pcm:
            return
        pcm_limit_bytes = self._pcm_audio_size_limit_bytes()
        if pcm_limit_bytes is not None and len(recording.pcm) > pcm_limit_bytes:
            logger.warning(
                "langsmith voice: skipped oversize pipecat audio for "
                "conversation_id=%r",
                conversation_id,
            )
            return
        wav = pcm_to_wav(
            bytes(recording.pcm), recording.sample_rate, recording.num_channels
        )
        self._attach_audio(
            tspan, name="conversation.wav", data=wav, mime_type=self._audio_mime_type
        )

    def _cleanup_conversation(self, trace_id: int, conversation_id: str) -> None:
        self._transcript_by_trace.pop(trace_id, None)
        self._audio_by_conversation.pop(conversation_id, None)
        self._forget_thread_id(trace_id)
