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
        ├── tool × N             (realtime: one per tool call, args → result)
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
Call :meth:`PipecatLangSmithSpanProcessor.instrument_user_aggregator` to supply
finalized user transcripts emitted outside those spans. A realtime tool call
arrives as two sibling spans, ``llm_tool_call`` (args) then
``llm_tool_result`` (output); the processor defers the call and merges the result
onto it, so each call renders as one ``tool`` run spanning call → result.
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
    iso_to_ns,
    parse_llm_messages,
    tool_message_key,
)

# Sort key for transcript entries: (epoch nanoseconds, sequence). Ordering the
# rollup by when each message actually occurred — rather than by the order spans
# arrive — keeps realtime user turns (whose transcripts land late, after the
# model has already replied) in their spoken position. ``seq`` breaks ties within
# one source (e.g. tool call before its result from the same snapshot).
_SortKey = tuple[int, int]

if TYPE_CHECKING:
    from pipecat.processors.aggregators.llm_response_universal import (  # type: ignore[import-not-found]
        LLMContextAggregatorPair,
        LLMUserAggregator,
        UserTurnMessageAddedMessage,
    )
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
        # trace_id -> the conversation the root renders, as ``(sort_key, message)``
        # entries ordered by when each message occurred (see ``_SortKey``).
        self._transcript_by_trace: MutableMapping[
            int, list[tuple[_SortKey, dict[str, Any]]]
        ] = TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)
        # conversation id -> merged PCM from an AudioBufferProcessor.
        self._audio_by_conversation: MutableMapping[str, _AudioRecord] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )
        # trace_id -> FIFO of deferred ``llm_tool_call`` spans, each held until
        # its ``llm_tool_result`` arrives so the two merge into one tool span.
        self._tool_calls_by_trace: MutableMapping[int, list[TranslatedSpan]] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )
        # thread id -> trace_id, so realtime user transcripts delivered outside
        # spans can find the conversation rollup they belong to.
        self._trace_by_thread: MutableMapping[str, int] = TTLCache(
            maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds
        )
        # thread id -> user turns (as ``(sort_key, message)``) that arrived before
        # their trace was known.
        self._pending_user_transcripts: MutableMapping[
            str, list[tuple[_SortKey, dict[str, Any]]]
        ] = TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)

    def _remember_thread_id(self, trace_id: int, thread_id: str) -> None:
        """Also index thread→trace, draining user turns buffered before the map."""
        super()._remember_thread_id(trace_id, thread_id)
        self._trace_by_thread[thread_id] = trace_id
        pending = self._pending_user_transcripts.pop(thread_id, None)
        for sort_key, message in pending or []:
            self._append_transcript(trace_id, message, sort_key)

    # -- realtime user transcript --------------------------------------------

    def instrument_user_aggregator(
        self, aggregator: LLMContextAggregatorPair, thread_id: str
    ) -> None:
        """Fold a realtime session's finalized user transcripts into its trace.

        Pipecat realtime services emit the user's finalized text through the user
        context aggregator's ``on_user_turn_message_added`` event rather than on
        an OTel span. Call this once after building the context aggregators::

            processor = configure_pipecat(...)
            aggregators = LLMContextAggregatorPair(context)
            set_thread_id(conversation_id)
            processor.instrument_user_aggregator(aggregators, conversation_id)

        The aggregator is the authoritative source of user turns: a realtime
        service transcribes the user's audio asynchronously, so the text lands
        (via this event, carrying the turn-start timestamp) after the model has
        already replied. The transcript is ordered by that timestamp, not arrival.

        Args:
            aggregator: the ``LLMContextAggregatorPair`` for the conversation.
            thread_id: the conversation id, matching :func:`set_thread_id`.
        """
        user_aggregator = aggregator.user()
        tid = str(thread_id)

        @user_aggregator.event_handler("on_user_turn_message_added")
        async def _on_user_turn_message_added(
            _aggregator: LLMUserAggregator, message: UserTurnMessageAddedMessage
        ) -> None:
            self._record_user_transcript(tid, message.content, message.timestamp)

    def _record_user_transcript(
        self, thread_id: str, text: str, timestamp: str
    ) -> None:
        """Append or buffer a finalized user turn, keyed by when it was spoken."""
        if not text:
            return
        message = build_user_message(text)
        sort_key = (iso_to_ns(timestamp), 0)
        trace_id = self._trace_by_thread.get(thread_id)
        if trace_id is None:
            pending = self._pending_user_transcripts.get(thread_id) or []
            pending.append((sort_key, message))
            self._pending_user_transcripts[thread_id] = pending
            return
        self._append_transcript(trace_id, message, sort_key)

    def _append_transcript(
        self, trace_id: int, message: dict[str, Any], sort_key: _SortKey
    ) -> None:
        """Add a message to the transcript the root renders, keyed for ordering."""
        conversation = self._transcript_by_trace.get(trace_id) or []
        conversation.append((sort_key, message))
        # Re-assign (not just mutate) so each turn refreshes the cache TTL.
        self._transcript_by_trace[trace_id] = conversation

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
        elif name == "llm_request":  # OpenAI realtime: history snapshot
            self._handle_llm_request(tspan, trace_id)
        elif name == "llm_setup":
            tspan.set_kind("chain")  # realtime wrapper
        elif name == "llm_tool_call":  # realtime: defer, merge with its result
            return self._handle_tool_call(tspan, trace_id)
        elif name == "llm_tool_result":
            return self._handle_tool_result(tspan, trace_id)
        return True

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """STT span: audio input → transcribed text."""
        transcript = tspan.attributes.get("transcript", "")
        is_final = tspan.attributes.get("is_final", True)
        tspan.set_kind("llm")
        tspan.set_messages(prompt=[build_user_message(f'Audio for: "{transcript}"')])
        if transcript:
            tspan.set_messages(completion=[build_assistant_message(str(transcript))])
            # Fold the finalized user turn into the rollup, keyed by when it was
            # transcribed. Realtime services emit only interim (is_final=False)
            # stt spans, so their user turns come from the aggregator instead;
            # this fold is the cascade path (STT→LLM→TTS, no aggregator).
            if is_final:
                self._append_transcript(
                    trace_id,
                    build_user_message(str(transcript)),
                    (tspan.span.start_time or 0, 0),
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

        # Cascade: the ``llm`` input already carries the whole ordered history, so
        # replace the transcript with this snapshot, keyed so the messages keep
        # their order and sort after earlier turns.
        transcript = [m for m in messages if m.get("role") != "system"]
        if output_data:
            transcript.append(build_completion_message(output_data))
        if transcript:
            base = tspan.span.start_time or 0
            self._transcript_by_trace[trace_id] = [
                ((base, i), message) for i, message in enumerate(transcript)
            ]

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
        """``llm_response`` span: conversation so far → realtime reply."""
        tspan.set_kind(self._llm_span_kind)
        conversation = self._render_messages(trace_id)
        if conversation:
            tspan.set_messages(prompt=conversation)

        output_data = tspan.attributes.get("output") or tspan.attributes.get(
            "text_output", ""
        )
        if output_data:
            completion = build_completion_message(output_data)
            tspan.set_messages(completion=[completion])
            self._append_transcript(
                trace_id, completion, (tspan.span.start_time or 0, 0)
            )

        usage = extract_llm_usage(tspan.attributes)
        if usage:
            tspan.set_usage(**usage)

    def _handle_llm_request(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """``llm_request`` span (OpenAI realtime): capture the tool round-trip.

        For OpenAI realtime, tool calls and results have no spans of their own —
        they exist only in this context snapshot. User turns come from the
        aggregator and assistant replies from ``llm_response``, so take *only* the
        tool-call / tool-result messages here, deduped by their id, keyed by this
        span's time so they sort after the user turn that triggered them.
        """
        tspan.set_kind("chain")
        messages = parse_llm_messages(tspan.attributes.get("input", ""))
        seen = {
            key
            for message in self._render_messages(trace_id)
            if (key := tool_message_key(message)) is not None
        }
        base = tspan.span.start_time or 0
        added = 0
        for message in messages:
            key = tool_message_key(message)
            if key is None or key in seen:
                continue
            seen.add(key)
            self._append_transcript(trace_id, message, (base, added))
            added += 1

    def _render_messages(self, trace_id: int) -> list[dict[str, Any]]:
        """Return the transcript as plain messages, ordered by sort key."""
        entries = self._transcript_by_trace.get(trace_id, [])
        return [message for _, message in sorted(entries, key=lambda e: e[0])]

    def _handle_tool_call(self, tspan: TranslatedSpan, trace_id: int) -> bool:
        """``llm_tool_call`` span: defer the call (args) until its result arrives."""
        tspan.set_kind("tool")
        function_name = tspan.attributes.get("tool.function_name")
        if function_name:
            tspan.set_name(str(function_name))
        arguments = tspan.attributes.get("tool.arguments")
        if arguments is not None:
            tspan.set_tool_input(arguments)
        self._tool_calls_by_trace.setdefault(trace_id, []).append(tspan)
        return False  # deferred; exported when its result arrives

    def _handle_tool_result(self, tspan: TranslatedSpan, trace_id: int) -> bool:
        """``llm_tool_result`` span: merge the result onto its deferred call span.

        Pairs with the oldest deferred call for the trace (Gemini Live puts no
        usable id on the result span, so pairing is by order). The result becomes
        the tool run's output and stretches the span to end at the result, so it
        spans call → result.
        """
        result = tspan.attributes.get("tool.result")
        call_tspan = self._take_pending_call(trace_id)
        if call_tspan is None:
            tspan.set_kind("tool")
            if result is not None:
                tspan.set_tool_output(result)
            return True

        if result is not None:
            call_tspan.set_tool_output(result)
        status = tspan.attributes.get("tool.result_status")
        if status is not None:
            call_tspan.set_metadata("tool_result_status", str(status))
        if tspan.span.end_time is not None:
            call_tspan.set_end_time(tspan.span.end_time)
        self._export(call_tspan)
        return False  # merged into the call span; drop this result span

    def _take_pending_call(self, trace_id: int) -> Optional[TranslatedSpan]:
        """Pop the oldest deferred call span for the trace, or ``None``."""
        queue = self._tool_calls_by_trace.get(trace_id)
        if not queue:
            return None
        call_tspan = queue.pop(0)
        if not queue:
            self._tool_calls_by_trace.pop(trace_id, None)
        return call_tspan

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

        messages = self._render_messages(trace_id)
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
        thread_id = self._thread_id_by_trace.get(trace_id)
        self._transcript_by_trace.pop(trace_id, None)
        self._audio_by_conversation.pop(conversation_id, None)
        if thread_id is not None:
            self._trace_by_thread.pop(thread_id, None)
            self._pending_user_transcripts.pop(thread_id, None)
        self._forget_thread_id(trace_id)
        self._flush_tool_calls(trace_id)

    def _flush_tool_calls(self, trace_id: Optional[int] = None) -> None:
        """Export held tool-call spans whose result never arrived (args only).

        Scoped to one trace at conversation end, or all held spans at shutdown.
        """
        trace_ids = (
            [trace_id] if trace_id is not None else list(self._tool_calls_by_trace)
        )
        for tid in trace_ids:
            for tspan in self._tool_calls_by_trace.pop(tid, None) or []:
                self._export(tspan)

    def shutdown(self) -> None:
        """Flush any still-held tool-call spans, then shut down downstream."""
        self._flush_tool_calls()
        super().shutdown()
