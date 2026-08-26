"""OTel → LangSmith bridge for LiveKit Agents.

Rewrites LiveKit's ``lk.*`` span data into the ``gen_ai.*`` / ``langsmith.*``
namespaces LangSmith ingests; non-LiveKit spans on the same provider pass
through untouched.

The root span is held open until the call recording arrives, then released with
the recording attached and its time origin stamped on it. A recording is
delivered one of two ways: :meth:`attach_session_report` (LiveKit's in-process
recorder, via ``ctx.make_session_report()`` in an ``on_session_end`` callback) or
:meth:`complete_recording` (LiveKit Egress, or any capture of your own). Shared
export / ``thread_id`` / message plumbing lives in
:class:`BaseLangSmithSpanProcessor`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import MutableMapping
from typing import Any, Optional

from cachetools import TTLCache
from opentelemetry.sdk.trace import SpanProcessor

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice._helpers import (
    build_assistant_message,
    build_user_message,
    try_parse_json_object,
)
from langsmith._internal.voice.base_span_processor import (
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)

from ._helpers import (
    build_message_from_event,
    build_messages_from_chat_history,
    extract_llm_usage,
    extract_model_from_lk_metrics,
    extract_provider_from_lk_metrics,
    extract_realtime_usage,
    flatten_lk_attributes_to_ls_metadata,
    is_livekit_span,
    normalize_provider,
)

# Lifetime / cap for per-conversation state; bounds memory for calls that never end.
DEFAULT_STATE_TTL_SECONDS = 3600.0
DEFAULT_STATE_MAXSIZE = 100_000

# How long a root span waits for its recording before being exported without
# one. Bounds the hold so a crashed job — or an ``on_session_end`` that never
# runs — yields a trace with no audio rather than no trace at all.
DEFAULT_RECORDING_TIMEOUT_SECONDS = 30.0

# LiveKit span names. Inference calls are ``llm``-kind; framework wrappers ``chain``.
_STT_SPAN = "user_turn"  # audio → transcript (inference)
_LLM_INFERENCE_SPAN = "llm_request"  # chat completion (inference)
_LLM_WRAPPER_SPANS = {"llm_node", "llm_request_run"}
_TTS_INFERENCE_SPAN = "tts_request"  # text → audio (inference)
_TTS_WRAPPER_SPANS = {"tts_node", "tts_request_run"}
_TURN_SPAN = "agent_turn"
_SESSION_SPAN = "agent_session"
_TOOL_SPAN = "function_tool"
_REALTIME_METRICS_SPAN = "realtime_metrics"
_USER_SPEAKING_SPAN = "user_speaking"

# ``llm_request`` emits one ``gen_ai.<role>.message`` event per chat item, plus a
# ``gen_ai.choice`` for the reply.
_LLM_EVENT_ROLES = {
    "gen_ai.system.message": "system",
    "gen_ai.user.message": "user",
    "gen_ai.assistant.message": "assistant",
    "gen_ai.tool.message": "tool",
}
_LLM_CHOICE_EVENT = "gen_ai.choice"

logger = logging.getLogger(__name__)


class LiveKitLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches LiveKit Agents' OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[SpanProcessor] = None,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        audio_mime_type: str = "audio/ogg",
        await_recording: bool = True,
        recording_timeout_seconds: float = DEFAULT_RECORDING_TIMEOUT_SECONDS,
        state_ttl_seconds: float = DEFAULT_STATE_TTL_SECONDS,
        **kwargs: Any,
    ) -> None:
        """Create the processor.

        Args:
            audio_mime_type: default MIME type for embedded recordings.
            await_recording: hold each root span until a recording is delivered
                by :meth:`attach_session_report` or :meth:`complete_recording`.
                Pass ``False`` when tracing a session with no audio, so its
                traces export immediately instead of waiting out the timeout.
            recording_timeout_seconds: how long that hold lasts before the root
                is exported without audio.
            state_ttl_seconds: lifetime for per-conversation state.
        """
        super().__init__(
            downstream_processor,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
            **kwargs,
        )
        self._audio_mime_type = audio_mime_type
        self._await_recording = await_recording
        self._recording_timeout_seconds = recording_timeout_seconds
        # Guards release: the timeout fires on a timer thread, while spans end
        # on the framework's asyncio loop, so both can reach _maybe_release.
        self._release_lock = threading.RLock()

        def _cache() -> Any:
            return TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)

        # trace_id -> running transcript, rolled up onto the root at session end.
        self._transcript_by_trace: MutableMapping[int, list[tuple[Any, dict]]] = (
            _cache()
        )
        # trace_id -> root span held open until the session (and any egress) ends.
        self._deferred_root_by_trace: MutableMapping[int, TranslatedSpan] = _cache()
        # trace_ids whose ``agent_session`` end span has arrived (used as a set).
        self._ended_session_traces: MutableMapping[int, bool] = _cache()
        # thread ids awaiting an egress recording (used as a set).
        self._threads_awaiting_recording: MutableMapping[str, bool] = _cache()
        # thread id -> pending egress audio bytes.
        self._pending_audio_by_thread: MutableMapping[str, dict] = _cache()
        # thread id -> trace_id, so ``complete_recording`` can find the trace.
        self._trace_by_thread: MutableMapping[str, int] = _cache()
        self._deferred_user_speaking: MutableMapping[str, list[TranslatedSpan]] = (
            _cache()
        )
        self._pending_user_transcripts: MutableMapping[str, list[str]] = _cache()
        # thread id -> recording start (epoch seconds), the audio's time origin.
        self._recording_started_at_by_thread: MutableMapping[str, float] = _cache()
        # thread id -> transcript built from a session report's chat history.
        self._chat_transcript_by_thread: MutableMapping[str, list[dict]] = _cache()
        # thread id -> why the recording did or didn't attach.
        self._audio_status_by_thread: MutableMapping[str, str] = _cache()
        # trace_id -> the timer that force-releases a root that waited too long.
        self._release_timers: dict[int, threading.Timer] = {}

    def _remember_thread_id(self, trace_id: int, thread_id: str) -> None:
        """Index thread→trace, and start awaiting this conversation's recording.

        Marking the thread here is what removes the old per-conversation
        ``expect_recording`` call: every traced conversation awaits a recording
        from the moment its first span starts.
        """
        super()._remember_thread_id(trace_id, thread_id)
        self._trace_by_thread[thread_id] = trace_id
        if self._await_recording and thread_id not in self._audio_status_by_thread:
            self._threads_awaiting_recording[thread_id] = True

    # -- realtime session instrumentation ------------------------------------

    def instrument_session(self, session: Any, thread_id: str) -> None:
        """Subscribe this processor to a LiveKit ``AgentSession``'s events.

        A realtime (speech-to-speech) model's user transcript arrives via the
        ``user_input_transcribed`` session event — never on a span — so without
        this the ``user_speaking`` spans render bare. Call it once after
        creating the session to wire the transcript in::

            processor = configure_livekit(...)
            session = AgentSession(llm=...)
            set_thread_id(conversation_id)
            processor.instrument_session(session, conversation_id)

        Each final transcript is paired FIFO with the next ``user_speaking`` span
        that has no transcript yet (we have no id to match a transcript to its
        exact span). No-op for the cascade pipeline, where the transcript already
        rides the STT ``user_turn`` span.

        This is about the *spans*. The root's transcript comes from the session
        report's chat history when one is supplied
        (:meth:`attach_session_report`), which already includes the realtime
        user's turns — so without a report, this is also the only way those
        turns reach the root.

        Args:
            session: the LiveKit ``AgentSession`` to subscribe to.
            thread_id: the conversation id, matching :func:`set_thread_id`.
        """

        @session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev: Any) -> None:
            if getattr(ev, "is_final", False):
                self._record_user_transcript(
                    str(thread_id), getattr(ev, "transcript", "") or ""
                )

    # -- recording delivery ---------------------------------------------------

    def attach_session_report(
        self,
        report: Any,
        thread_id: str,
    ) -> None:
        """Attach a LiveKit ``SessionReport`` and release the held root.

        Call once per conversation from an ``on_session_end`` callback, where
        the recorder has closed and the report is complete::

            processor = configure_livekit()


            async def on_session_end(ctx: JobContext) -> None:
                processor.attach_session_report(
                    ctx.make_session_report(), thread_id=ctx.room.name
                )


            server = AgentServer()


            @server.rtc_session(on_session_end=on_session_end)
            async def entrypoint(ctx: JobContext) -> None: ...

        Reads the recording's time origin (so the trace audio player lines up
        with the waterfall), embeds the recording itself, and rolls the report's
        chat history up as the root's transcript.

        A report always carries the chat history, but only carries a recording
        when LiveKit's own recorder made one. If it has no recording, the root
        stays held for a :meth:`complete_recording` call — so recording with
        egress means calling *both*: this for the transcript, then
        ``complete_recording`` with the audio, which releases the trace with
        both. Pass ``await_recording=False`` to :func:`configure_livekit` when
        the conversation has no audio at all.

        Args:
            report: LiveKit's ``SessionReport`` (duck-typed — the module never
                imports it, so it stays importable without ``livekit-agents``).
            thread_id: the conversation id, matching :func:`set_thread_id`.
        """
        thread = str(thread_id)

        started_at = getattr(report, "audio_recording_started_at", None)
        audio_path = getattr(report, "audio_recording_path", None)
        history = getattr(report, "chat_history", None)

        status = "none"
        data = None
        if audio_path is not None:
            # Read the file before taking the lock — it is the slow part, and it
            # touches none of the shared state.
            data, status = self._read_audio_file(audio_path)
        messages = build_messages_from_chat_history(history) if history else []

        # Everything this delivery contributes lands as one atomic unit, so a
        # concurrent delivery can never release a root halfway through it.
        with self._release_lock:
            if isinstance(started_at, (int, float)):
                self._recording_started_at_by_thread[thread] = float(started_at)
            if data:
                self._pending_audio_by_thread[thread] = {
                    "name": getattr(audio_path, "name", "recording.ogg"),
                    "data": data,
                    "mime_type": self._audio_mime_type,
                }
            if messages:
                self._chat_transcript_by_thread[thread] = messages
            return self._finish_report(thread, status, audio_path)

    def _finish_report(self, thread: str, status: str, audio_path: Any) -> None:
        """Release for a session report, unless its audio is coming separately."""
        if audio_path is None and self._await_recording:
            # The report carried no recording, so LiveKit's own recorder was not
            # the capture: the audio is arriving separately, from an egress
            # upload handed to ``complete_recording``. Keep the root held for it
            # — everything above is already stored, so that later call releases
            # a trace with both the recording and this transcript. The timeout
            # still bounds the wait, and ``await_recording=False`` says up front
            # that no audio is coming.
            return
        self._finish_recording(thread, status)

    def complete_recording(
        self,
        thread_id: str,
        data: Optional[bytes],
        *,
        name: str = "recording.ogg",
        mime_type: Optional[str] = None,
        started_at: Optional[float] = None,
    ) -> None:
        """Attach a recording supplied as bytes and release the held root.

        For LiveKit Egress, or any capture of your own. ``data`` is the
        recording bytes, or ``None`` to release without audio. ``thread_id``
        must match :func:`set_thread_id`. Safe to call before or after the
        session ends.

        ``started_at`` is when the recording's first sample was captured (epoch
        seconds). Without it the trace audio player has to assume the recording
        starts when the trace does, which it generally does not.
        """
        thread = str(thread_id)
        with self._release_lock:
            if isinstance(started_at, (int, float)):
                self._recording_started_at_by_thread[thread] = float(started_at)
            status = "none"
            if data:
                self._pending_audio_by_thread[thread] = {
                    "name": name,
                    "data": bytes(data),
                    "mime_type": mime_type or self._audio_mime_type,
                }
                status = "attached"
            self._finish_recording(thread, status)

    def _finish_recording(self, thread: str, status: str) -> None:
        """Stop awaiting this thread's recording and release its root."""
        self._audio_status_by_thread[thread] = status
        self._threads_awaiting_recording.pop(thread, None)
        trace_id = self._trace_by_thread.get(thread)
        if trace_id is None:
            logger.warning(
                "langsmith voice: nothing to attach a recording to for thread "
                "%s — its trace was already exported, or this thread id never "
                "matched one. Deliver the recording before the trace is "
                "released, and check the id matches set_thread_id().",
                thread,
            )
            return
        self._maybe_release(trace_id)

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        trace_id = tspan.span.context.trace_id
        name = tspan.span.name

        if name == _STT_SPAN:
            self._handle_stt(tspan)
        elif name == _LLM_INFERENCE_SPAN:
            self._handle_llm_request(tspan)
        elif name in _LLM_WRAPPER_SPANS:
            tspan.set_kind("chain")  # wrappers: no fabricated I/O
        elif name == _TTS_INFERENCE_SPAN:
            self._handle_tts(tspan)
        elif name in _TTS_WRAPPER_SPANS:
            tspan.set_kind("chain")  # wrappers: no fabricated I/O
        elif name == _TURN_SPAN:
            self._handle_turn(tspan)
        elif name == _USER_SPEAKING_SPAN:
            return self._handle_user_speaking(tspan)
        elif name == _SESSION_SPAN:
            # Session end: release the deferred root, then export this span.
            tspan.set_kind("chain")
            self._ended_session_traces[trace_id] = True
            self._flush_user_speaking(self._thread_id_by_trace.get(trace_id))
            self._maybe_release(trace_id)
        elif name == "eou_detection":
            tspan.set_kind("chain")  # framework step
        elif name == _TOOL_SPAN:
            self._handle_tool(tspan)
        elif name == _REALTIME_METRICS_SPAN:
            tspan.set_kind("llm")
        elif tspan.span.parent is None and is_livekit_span(tspan.span):
            # Conversation root — _handle_root owns its export (False). Gated on
            # the LiveKit scope so a non-LiveKit parentless span isn't hijacked.
            self._handle_root(tspan, trace_id)
            return False
        return True  # non-LiveKit span: export untouched

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, tspan: TranslatedSpan) -> None:
        """STT (``user_turn``): audio input → transcribed text."""
        tspan.set_kind("llm")
        tspan.set_model(tspan.attributes.get("gen_ai.request.model"))
        tspan.set_provider(
            normalize_provider(tspan.attributes.get("gen_ai.provider.name"))
        )

        transcript = tspan.attributes.get("lk.user_transcript")
        if transcript:
            tspan.set_messages(
                prompt=[build_user_message(f'Audio for: "{transcript}"')]
            )
            tspan.set_messages(completion=[build_assistant_message(str(transcript))])
        tspan.exclude_from_message_view()

    def _handle_llm_request(self, tspan: TranslatedSpan) -> None:
        """``llm_request``: rebuild prompt/completion from the gen_ai.* events.

        The translated events are then stripped so the ingester doesn't render
        them twice.
        """
        tspan.set_kind("llm")

        prompt: list[dict] = []
        completion: list[dict] = []
        for event in tspan.events:
            if event.name == _LLM_CHOICE_EVENT:
                completion.append(build_message_from_event("assistant", event))
            elif (role := _LLM_EVENT_ROLES.get(event.name)) is not None:
                prompt.append(build_message_from_event(role, event))
        tspan.set_messages(prompt=prompt or None, completion=completion or None)

        provider = extract_provider_from_lk_metrics(
            tspan.attributes.get("lk.llm_metrics")
        )
        tspan.set_provider(normalize_provider(provider))

        # Lift the token usage (counts + cache_read detail) from the metrics blob.
        usage = extract_llm_usage(tspan.attributes.get("lk.llm_metrics"))
        if usage:
            tspan.set_usage(**usage)

        tspan.events[:] = [
            e
            for e in tspan.events
            if e.name != _LLM_CHOICE_EVENT and e.name not in _LLM_EVENT_ROLES
        ]

    def _handle_tts(self, tspan: TranslatedSpan) -> None:
        """``tts_request``: synthesize text → audio (an ``llm`` inference)."""
        tspan.set_kind("llm")
        tspan.exclude_from_message_view()

        text = (
            tspan.attributes.get("lk.input_text")
            or tspan.attributes.get("lk.request.text")
            or tspan.attributes.get("lk.text")
            or ""
        )
        tspan.set_messages(
            prompt=[build_user_message(str(text))],
            completion=[build_assistant_message(f'Generated audio for: "{text}"')],
        )

        tspan.set_model(
            tspan.attributes.get("gen_ai.request.model")
            or extract_model_from_lk_metrics(tspan.attributes.get("lk.tts_metrics"))
        )
        provider = extract_provider_from_lk_metrics(
            tspan.attributes.get("lk.tts_metrics")
        )
        tspan.set_provider(normalize_provider(provider))

    def _handle_turn(self, tspan: TranslatedSpan) -> None:
        """Render an ``agent_turn`` and append it to the running transcript.

        ``llm`` for a realtime model (the turn is the model call, usage stamped
        here); ``chain`` for cascade (the STT/LLM/TTS children carry their usage).
        """
        tspan.set_kind(
            "llm" if "lk.realtime_model_metrics" in tspan.attributes else "chain"
        )

        user_input = tspan.attributes.get("lk.user_input")
        response = tspan.attributes.get("lk.response.text")
        trace_id = tspan.span.context.trace_id
        start = tspan.span.start_time
        if user_input:
            msg = build_user_message(str(user_input))
            tspan.set_messages(prompt=[msg])
            self._append_transcript(trace_id, msg, start)
        if response:
            msg = build_assistant_message(str(response))
            tspan.set_messages(completion=[msg])
            self._append_transcript(trace_id, msg, start)

    def _append_transcript(self, trace_id: int, message: dict, sort_key: Any) -> None:
        """Append a message to the transcript the root rolls up, keyed for ordering."""
        conversation = self._transcript_by_trace.get(trace_id) or []
        conversation.append((sort_key, message))
        # Re-assign (not just mutate) so each turn refreshes the cache TTL.
        self._transcript_by_trace[trace_id] = conversation

    # -- realtime user transcript (speech-to-speech) --------------------------

    def _handle_user_speaking(self, tspan: TranslatedSpan) -> bool:
        """Handle a ``user_speaking`` span — the realtime user turn.

        Deferred (``False``): stamp+export now if the transcript was already
        buffered, else hold it until one is fed (or flushed untouched at session
        end). Exported as-is (``True``) when there's no thread id to pair against.
        """
        tspan.set_kind("chain")
        thread = tspan.attributes.get("langsmith.metadata.thread_id")
        if thread is None:
            return True
        thread = str(thread)

        pending = self._pending_user_transcripts.get(thread)
        if pending:
            transcript = pending.pop(0)
            if pending:
                self._pending_user_transcripts[thread] = pending
            else:
                self._pending_user_transcripts.pop(thread, None)
            self._apply_user_transcript(tspan, transcript)
            self._export(tspan)
            return False

        held = self._deferred_user_speaking.get(thread) or []
        held.append(tspan)
        self._deferred_user_speaking[thread] = held
        return False

    def _record_user_transcript(self, thread_id: str, transcript: str) -> None:
        """Pair a realtime transcript (from ``instrument_session``) with its span.

        Applies it to the oldest held ``user_speaking`` span for the thread, or
        buffers it if that span hasn't ended yet.
        """
        tid = str(thread_id)
        held = self._deferred_user_speaking.get(tid)
        if held:
            tspan = held.pop(0)
            if held:
                self._deferred_user_speaking[tid] = held
            else:
                self._deferred_user_speaking.pop(tid, None)
            self._apply_user_transcript(tspan, transcript)
            self._export(tspan)
            return
        pending = self._pending_user_transcripts.get(tid) or []
        pending.append(transcript)
        self._pending_user_transcripts[tid] = pending

    def _apply_user_transcript(self, tspan: TranslatedSpan, transcript: str) -> None:
        """Render a fed transcript onto a ``user_speaking`` span as the user's turn.

        Unlike the cascade STT ``user_turn`` (which is excluded), this is the only
        record of the realtime user's words, so it's shown — as a plain ``user``
        message. An empty transcript renders no fabricated I/O.
        """
        tspan.set_kind("llm")
        if transcript:
            tspan.attributes["lk.user_transcript"] = transcript
            msg = build_user_message(transcript)
            tspan.set_messages(prompt=[msg])
            # Also feed the span-derived rollup. That rollup is only read when
            # no session report was supplied (see ``_render_conversation``), so
            # this line does nothing on the report path and is the realtime
            # user's only route into the root transcript on the egress path.
            self._append_transcript(
                tspan.span.context.trace_id, msg, tspan.span.start_time
            )

    def _flush_user_speaking(self, thread_id: Optional[str]) -> None:
        """Export held ``user_speaking`` spans untranscribed (no transcript arrived)."""
        if thread_id is None:
            return
        tid = str(thread_id)
        for tspan in self._deferred_user_speaking.pop(tid, None) or []:
            self._export(tspan)
        self._pending_user_transcripts.pop(tid, None)

    def _handle_tool(self, tspan: TranslatedSpan) -> None:
        """``function_tool``: render as a proper ``tool`` run with its I/O."""
        tspan.set_kind("tool")
        tool_name = tspan.attributes.get("lk.function_tool.name")
        if tool_name:
            tspan.set_metadata("tool_name", str(tool_name))
        args = tspan.attributes.get("lk.function_tool.arguments")
        if args is not None:
            tspan.set_tool_input(args)
        output = tspan.attributes.get("lk.function_tool.output")
        if output is not None:
            tspan.set_tool_output(output)

    # -- deferred root release ------------------------------------------------

    def _handle_root(self, tspan: TranslatedSpan, trace_id: int) -> None:
        """Mark the conversation root and defer it until the session ends."""
        tspan.set_kind("chain")
        tspan.set_root_span(True)
        tspan.set_metadata("ls_modality", "audio")
        tspan.set_metadata("ls_integration", "livekit")
        tspan.set_metadata(
            "ls_integration_version", (get_package_version("livekit-agents") or "")
        )

        self._deferred_root_by_trace[trace_id] = tspan
        self._maybe_release(trace_id)

    def _maybe_release(self, trace_id: int, *, force: bool = False) -> None:
        """Export the deferred root once the session ended and audio is ready.

        Requires the root seen, the session ended, and no awaited recording.
        While a recording is still awaited this arms the timeout that releases
        the root without one. ``force`` skips both gates — the last-resort path
        at :meth:`shutdown` for a root that never completed.
        """
        with self._release_lock:
            tspan = self._deferred_root_by_trace.get(trace_id)
            if tspan is None:
                return
            thread = self._thread_id_by_trace.get(trace_id)
            if not force:
                if trace_id not in self._ended_session_traces:
                    return
                if thread is not None and thread in self._threads_awaiting_recording:
                    self._schedule_release_timeout(trace_id)
                    return  # still waiting for a recording

            self._cancel_release_timer(trace_id)
            self._deferred_root_by_trace.pop(trace_id, None)
            self._render_conversation(tspan, thread)
            if thread is not None:
                self._attach_pending_audio(tspan, thread)
                self._stamp_recording_origin(tspan, thread)
            self._export(tspan)
            self._cleanup_trace(trace_id)

    def _schedule_release_timeout(self, trace_id: int) -> None:
        """Arm the one-shot timer that releases a root whose audio never came."""
        if trace_id in self._release_timers or self._recording_timeout_seconds <= 0:
            return
        timer = threading.Timer(
            self._recording_timeout_seconds, self._on_recording_timeout, (trace_id,)
        )
        timer.daemon = True
        self._release_timers[trace_id] = timer
        timer.start()

    def _on_recording_timeout(self, trace_id: int) -> None:
        """Give up waiting for a recording and export the root without one."""
        with self._release_lock:
            self._release_timers.pop(trace_id, None)
            thread = self._thread_id_by_trace.get(trace_id)
            if thread is not None:
                if thread not in self._threads_awaiting_recording:
                    return  # a recording landed just as the timer fired
                logger.warning(
                    "langsmith voice: no recording for thread %s after %.1fs; "
                    "exporting the trace without audio. Call "
                    "attach_session_report() or complete_recording() at session "
                    "end, or pass await_recording=False if this session has no "
                    "audio.",
                    thread,
                    self._recording_timeout_seconds,
                )
                self._audio_status_by_thread[thread] = "timeout"
                self._threads_awaiting_recording.pop(thread, None)
            self._maybe_release(trace_id)

    def _cancel_release_timer(self, trace_id: int) -> None:
        """Cancel a pending timeout (the recording arrived, or we're shutting down)."""
        timer = self._release_timers.pop(trace_id, None)
        if timer is not None:
            timer.cancel()

    def _stamp_recording_origin(self, tspan: TranslatedSpan, thread: str) -> None:
        """Stamp where the recording sits on the trace's timeline, and why.

        LiveKit's recorder starts inside ``session.start()`` — after room
        connect and agent setup — so the recording's first sample is seconds
        later than the root span's start. Without the offset the trace audio
        player has to assume they coincide, and playback runs ahead of the
        waterfall by that gap.
        """
        status = self._audio_status_by_thread.get(thread)
        if status:
            tspan.set_metadata("ls_audio_attach_status", status)
        started_at = self._recording_started_at_by_thread.get(thread)
        root_start_ns = tspan.span.start_time
        if started_at is None or root_start_ns is None:
            return
        # Both values come from ``time.time()`` in the agent process and the
        # root's start_time is from that same process and clock, so the
        # difference holds even under wall-clock skew. Never turn this into a
        # cross-host comparison.
        root_start_s = root_start_ns / 1e9
        tspan.set_metadata("ls_audio_recording_started_at", started_at)
        tspan.set_metadata(
            "ls_audio_recording_start_offset_ms",
            round((started_at - root_start_s) * 1000),
        )

    def _render_conversation(
        self, tspan: TranslatedSpan, thread: Optional[str] = None
    ) -> bool:
        """Set the conversation transcript as the root's input.

        Prefers a session report's chat history — it is ordered by the messages'
        own timestamps and carries the tool calls — and falls back to the
        transcript assembled from spans when no report was supplied.
        """
        if thread is not None:
            messages = self._chat_transcript_by_thread.get(thread)
            if messages:
                tspan.set_messages(prompt=messages)
                return True
        entries = self._transcript_by_trace.get(tspan.span.context.trace_id, [])
        if not entries:
            return False
        tspan.set_messages(
            prompt=[msg for _, msg in sorted(entries, key=lambda e: e[0])]
        )
        return True

    def _cleanup_trace(self, trace_id: int) -> None:
        # Read the thread id before ``_forget_thread_id`` drops it from the base map.
        thread = self._thread_id_by_trace.get(trace_id)
        self._transcript_by_trace.pop(trace_id, None)
        self._forget_thread_id(trace_id)
        self._ended_session_traces.pop(trace_id, None)
        self._cancel_release_timer(trace_id)
        if thread is not None:
            self._trace_by_thread.pop(thread, None)
            self._threads_awaiting_recording.pop(thread, None)
            self._pending_audio_by_thread.pop(thread, None)
            self._recording_started_at_by_thread.pop(thread, None)
            self._chat_transcript_by_thread.pop(thread, None)
            self._audio_status_by_thread.pop(thread, None)
            self._flush_user_speaking(thread)

    def shutdown(self) -> None:
        """Force-export any still-held roots and user_speaking spans, then shut down.

        ``force_flush`` deliberately does not — a still-held root there is
        legitimately in progress, not a buffered export waiting to drain.
        """
        for trace_id in list(self._release_timers):
            self._cancel_release_timer(trace_id)
        for trace_id in list(self._deferred_root_by_trace):
            self._maybe_release(trace_id, force=True)
        for thread in list(self._deferred_user_speaking.keys()):
            self._flush_user_speaking(thread)
        super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force-flush the downstream — deferred root spans are NOT finalized."""
        return super().force_flush(timeout_millis)

    # -- audio attachment -----------------------------------------------------

    def _read_audio_file(self, path: Any) -> tuple[Optional[bytes], str]:
        """Read a recording from disk, size-checked *before* it is loaded.

        Returns ``(bytes, "attached")`` or ``(None, reason)``. The size is
        checked with ``stat()`` first so an oversize recording is never read
        into memory. Callers inline the returned bytes — the path itself must
        never reach the LangSmith client, which rejects filesystem-referencing
        attachments unless ``dangerously_allow_filesystem=True``
        (see ``_reject_filesystem_attachments`` / GHSA-f4xh-w4cj-qxq8).
        """
        try:
            size = path.stat().st_size
        except Exception:
            logger.warning("langsmith voice: no readable recording at %s.", path)
            return None, "unreadable"
        if (
            self.audio_size_limit_bytes is not None
            and size > self.audio_size_limit_bytes
        ):
            logger.warning(
                "langsmith voice: recording at %s is %d bytes, over the "
                "%d-byte limit; skipping the attachment.",
                path,
                size,
                self.audio_size_limit_bytes,
            )
            return None, "too_large"
        try:
            return path.read_bytes(), "attached"
        except Exception:
            logger.warning(
                "langsmith voice: failed reading the recording at %s.",
                path,
                exc_info=True,
            )
            return None, "unreadable"

    def _attach_pending_audio(self, tspan: TranslatedSpan, thread: str) -> None:
        """Embed the recording delivered for this conversation, if any."""
        pending = self._pending_audio_by_thread.pop(thread, None)
        if not pending or not pending.get("data"):
            return
        self._attach_audio(
            tspan,
            name=pending["name"],
            data=pending["data"],
            mime_type=pending["mime_type"],
        )

    def _pre_export(self, tspan: TranslatedSpan) -> None:
        """Forward ``lk.*`` to ``langsmith.metadata.lk_*`` and normalize the provider.

        Scalars pass through; JSON-object blobs are flattened per field. Runs on
        every exported span, so it also covers spans no handler classified.
        """
        for key in list(tspan.attributes.keys()):
            if not key.startswith("lk."):
                continue
            value = tspan.attributes[key]
            flat_key = f"langsmith.metadata.{key.replace('.', '_')}"
            parsed = try_parse_json_object(value)
            if parsed is not None:
                for name, val in flatten_lk_attributes_to_ls_metadata(
                    parsed, flat_key
                ).items():
                    if name not in tspan.attributes:  # don't clobber what a branch set
                        tspan.attributes[name] = val
                continue
            if flat_key in tspan.attributes:  # don't clobber what a branch set
                continue
            tspan.attributes[flat_key] = value

        # Normalize + cross-fill both provider keys from whichever LiveKit set.
        provider = normalize_provider(
            tspan.attributes.get("gen_ai.provider.name")
        ) or normalize_provider(tspan.attributes.get("gen_ai.system"))
        tspan.set_provider(provider)

        # Lift realtime usage wherever LiveKit stamps the blob (agent_turn, or an
        # orphaned realtime_metrics span). Idempotent: skipped once usage is set.
        if (
            "lk.realtime_model_metrics" in tspan.attributes
            and "langsmith.usage_metadata" not in tspan.attributes
        ):
            usage = extract_realtime_usage(
                tspan.attributes["lk.realtime_model_metrics"]
            )
            if usage:
                tspan.set_usage(**usage)
