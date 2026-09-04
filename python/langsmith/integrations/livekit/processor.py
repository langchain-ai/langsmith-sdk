"""OTel → LangSmith bridge for LiveKit Agents.

Rewrites LiveKit's ``lk.*`` span data into the ``gen_ai.*`` / ``langsmith.*``
namespaces LangSmith ingests; non-LiveKit spans on the same provider pass
through untouched.

The root span is held until the processor's AgentSession close hook captures
its session report. LiveKit's recorder supplies audio on that report; egress
audio arrives separately through :meth:`complete_recording`. Shared export /
``thread_id`` / message plumbing lives in :class:`BaseLangSmithSpanProcessor`.
"""

from __future__ import annotations

import logging
import threading
import warnings
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any, Literal, Optional, get_args

from cachetools import TTLCache
from opentelemetry.context import Context
from opentelemetry.sdk.trace import Span, SpanProcessor

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
from ._state import _ConversationState, _PendingAudio, _PendingThreadState

# Lifetime / cap for per-conversation state; bounds memory for calls that never end.
DEFAULT_STATE_TTL_SECONDS = 3600.0
DEFAULT_STATE_MAXSIZE = 100_000

# How long a root span waits for its session data before being exported.
DEFAULT_RECORDING_TIMEOUT_SECONDS = 30.0

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

_LLM_EVENT_ROLES = {
    "gen_ai.system.message": "system",
    "gen_ai.user.message": "user",
    "gen_ai.assistant.message": "assistant",
    "gen_ai.tool.message": "tool",
}
_LLM_CHOICE_EVENT = "gen_ai.choice"

logger = logging.getLogger(__name__)

RecordingMode = Literal["session_report", "egress", "none"]
_RECORDING_MODES = frozenset(get_args(RecordingMode))


class LiveKitLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches LiveKit Agents' OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[SpanProcessor] = None,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        audio_path_provider: Optional[Callable[[], Optional[Path]]] = None,
        audio_mime_type: str = "audio/ogg",
        recording_mode: RecordingMode = "session_report",
        recording_timeout_seconds: float = DEFAULT_RECORDING_TIMEOUT_SECONDS,
        state_ttl_seconds: float = DEFAULT_STATE_TTL_SECONDS,
        **kwargs: Any,
    ) -> None:
        """Create the processor.

        Args:
            audio_path_provider: Deprecated compatibility parameter. It is ignored.
            audio_mime_type: default MIME type for embedded recordings.
            recording_mode: where recordings come from: ``"session_report"``
                for LiveKit's recorder, ``"egress"`` for bytes supplied with
                :meth:`complete_recording`, or ``"none"`` for report data
                without audio. This is the default for every conversation;
                :meth:`expect_recording` can override one thread to egress.
            recording_timeout_seconds: how long the root waits for required
                session data before it is exported.
            state_ttl_seconds: lifetime for per-conversation state.
        """
        if audio_path_provider is not None:
            warnings.warn(
                "audio_path_provider is deprecated and ignored.",
                DeprecationWarning,
                stacklevel=2,
            )

        super().__init__(
            downstream_processor,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
            **kwargs,
        )
        if recording_mode not in _RECORDING_MODES:
            raise ValueError(
                f"recording_mode must be one of {sorted(_RECORDING_MODES)!r}"
            )
        if recording_timeout_seconds <= 0:
            raise ValueError("recording_timeout_seconds must be greater than zero")
        self._audio_mime_type = audio_mime_type
        self._recording_mode = recording_mode
        self._recording_timeout_seconds = recording_timeout_seconds
        # The timeout fires on a timer thread; every conversation-state mutation
        # uses this lock, including the framework's normal span callbacks.
        self._state_lock = threading.RLock()
        # Serialize the full claim-and-export operation with downstream shutdown.
        # This is separate from ``_state_lock`` so exporter I/O does not block
        # unrelated conversation-state updates. When both are needed, acquire
        # this lock first.
        self._export_lock = threading.RLock()

        def _cache() -> Any:
            return TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)

        self._state_by_trace: MutableMapping[int, _ConversationState] = _cache()
        self._trace_by_thread: MutableMapping[str, int] = _cache()
        # ``expect_recording`` and ``complete_recording`` are legacy APIs that
        # may be called before LiveKit starts the first span for a conversation.
        self._thread_state_waiting_for_trace: MutableMapping[
            str, _PendingThreadState
        ] = _cache()
        # Distinguish a genuinely early legacy delivery from one that arrived
        # after its trace was already exported (which must not leak into a later
        # conversation that reuses the same thread id).
        self._completed_threads: MutableMapping[str, bool] = _cache()
        # A transcript event may arrive after instrument_session() but before a
        # LiveKit span has given us that thread's trace id.
        self._transcripts_waiting_for_trace: MutableMapping[str, list[str]] = _cache()

    def _get_state(self, trace_id: int) -> Optional[_ConversationState]:
        return self._state_by_trace.get(trace_id)

    def _get_or_create_state(self, trace_id: int) -> _ConversationState:
        state = self._get_state(trace_id)
        if state is not None:
            self._associate_thread_with_state(
                state, self._thread_id_by_trace.get(trace_id)
            )
            return state

        state = _ConversationState(
            trace_id=trace_id, recording_mode=self._recording_mode
        )
        self._associate_thread_with_state(state, self._thread_id_by_trace.get(trace_id))
        self._state_by_trace[trace_id] = state
        return state

    def _associate_thread_with_state(
        self, state: _ConversationState, thread_id: Optional[str]
    ) -> None:
        if thread_id is None or state.thread_id == thread_id:
            return
        if state.thread_id is not None:
            logger.warning(
                "langsmith voice: trace %x is already bound to thread %s; "
                "ignoring a second thread id %s.",
                state.trace_id,
                state.thread_id,
                thread_id,
            )
            return

        existing_state = self._get_state_by_thread(thread_id)
        if existing_state is not None and existing_state is not state:
            logger.warning(
                "langsmith voice: thread id %s is already bound to an active "
                "LiveKit trace; recordings require one active trace per thread.",
                thread_id,
            )
            return

        state.thread_id = thread_id
        self._completed_threads.pop(thread_id, None)
        self._trace_by_thread[thread_id] = state.trace_id
        waiting = self._transcripts_waiting_for_trace.pop(thread_id, None)
        if waiting:
            state.transcripts_waiting_for_span.extend(waiting)
        pending = self._thread_state_waiting_for_trace.pop(thread_id, None)
        if pending is not None:
            if pending.recording_mode is not None:
                state.recording_mode = pending.recording_mode
            if pending.recording_received:
                state.pending_audio = pending.pending_audio
                state.recording_started_at = pending.recording_started_at
                state.audio_status = pending.audio_status
                state.recording_received = True

    def _get_state_by_thread(self, thread_id: str) -> Optional[_ConversationState]:
        trace_id = self._trace_by_thread.get(thread_id)
        if trace_id is None:
            return None
        state = self._state_by_trace.get(trace_id)
        if state is None or state.thread_id != thread_id:
            self._trace_by_thread.pop(thread_id, None)
            return None
        return state

    def _refresh_state(self, state: _ConversationState) -> None:
        self._state_by_trace[state.trace_id] = state

    def _remember_thread_id(self, trace_id: int, thread_id: str) -> None:
        """Capture a late thread id and merge any pre-trace lifecycle data."""
        super()._remember_thread_id(trace_id, thread_id)
        with self._state_lock:
            state = self._get_state(trace_id)
            if state is not None:
                self._associate_thread_with_state(state, thread_id)
                self._refresh_state(state)

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        """Capture thread context and install the session-report close hook."""
        super().on_start(span, parent_context)
        if span.name != _SESSION_SPAN:
            return
        try:
            self._install_session_report_hook(span.context.trace_id)
        except Exception:
            # Lifecycle instrumentation must never prevent a LiveKit session
            # from starting. The release timeout remains the failure fallback.
            logger.warning(
                "langsmith voice: failed installing the automatic LiveKit "
                "session-report callback.",
                exc_info=True,
            )

    def _install_session_report_hook(self, trace_id: int) -> None:
        """Attach one additive close listener to the active AgentSession."""
        try:
            from livekit.agents import get_job_context  # type: ignore[import-not-found]
        except ImportError:
            return

        job_ctx = get_job_context(required=False)
        if job_ctx is None:
            return
        session = getattr(job_ctx, "_primary_agent_session", None)
        if session is None:
            try:
                session = job_ctx.primary_session
            except (AttributeError, RuntimeError):
                return

        session_id = id(session)
        with self._state_lock:
            state = self._get_or_create_state(trace_id)
            if state.report_hook_session_id == session_id:
                return
            state.report_hook_session_id = session_id
            self._refresh_state(state)

        def _capture_report(*_: Any) -> None:
            try:
                report = job_ctx.make_session_report(session)
                self._attach_session_report_to_trace(
                    report, trace_id=trace_id, expected_state=state
                )
            except Exception:
                logger.warning(
                    "langsmith voice: failed capturing the automatic LiveKit "
                    "session report.",
                    exc_info=True,
                )

        try:
            session.once("close", _capture_report)
        except Exception:
            with self._state_lock:
                current = self._get_state(trace_id)
                if current is state and current.report_hook_session_id == session_id:
                    current.report_hook_session_id = None
                    self._refresh_state(current)
            raise

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

    def attach_session_report(
        self,
        report: Any,
        thread_id: str,
    ) -> None:
        """Attach a LiveKit session report to the held conversation root.

        The report supplies chat history in every recording mode. In
        ``session_report`` mode it also supplies the recording; egress audio is
        delivered separately through :meth:`complete_recording`.

        Args:
            report: LiveKit's ``SessionReport`` (duck-typed — the module never
                imports it, so it stays importable without ``livekit-agents``).
            thread_id: the conversation id, matching :func:`set_thread_id`.
        """
        thread = str(thread_id)
        with self._state_lock:
            state = self._get_state_by_thread(thread)
            if state is None:
                if self._completed_threads.get(thread):
                    # An older user callback may deliver the same report after
                    # the automatic close hook has already exported the trace.
                    return
                self._warn_missing_conversation(thread, "session report")
                return
            trace_id = state.trace_id
        self._attach_session_report_to_trace(
            report, trace_id=trace_id, expected_state=state
        )

    def _attach_session_report_to_trace(
        self,
        report: Any,
        *,
        trace_id: int,
        expected_state: _ConversationState,
    ) -> None:
        """Commit a report to the exact state captured by a lifecycle hook."""
        with self._state_lock:
            state = self._get_state(trace_id)
            if state is not expected_state or state.report_received:
                return
            read_report_audio = state.recording_mode == "session_report"

        history = getattr(report, "chat_history", None)
        messages = build_messages_from_chat_history(history) if history else []
        report_audio = (
            self._audio_from_session_report(report)
            if read_report_audio
            else (None, None, None)
        )

        with self._state_lock:
            state = self._get_state(trace_id)
            if state is not expected_state or state.report_received:
                return
            state.report_transcript = messages
            state.report_received = True
            if state.recording_mode == "session_report":
                (
                    state.pending_audio,
                    state.recording_started_at,
                    state.audio_status,
                ) = report_audio
            self._refresh_state(state)
        self._export_conversation_if_ready(trace_id)

    def expect_recording(self, thread_id: str) -> None:
        """Mark one conversation as awaiting :meth:`complete_recording`.

        This legacy API overrides the processor's default recording mode for
        only ``thread_id``. It may be called before LiveKit starts any spans.
        """
        thread = str(thread_id)
        with self._state_lock:
            state = self._get_state_by_thread(thread)
            if state is None:
                self._completed_threads.pop(thread, None)
                pending = self._thread_state_waiting_for_trace.get(thread)
                if pending is None:
                    pending = _PendingThreadState()
                pending.recording_mode = "egress"
                self._thread_state_waiting_for_trace[thread] = pending
                return
            state.recording_mode = "egress"
            if state.report_received and not state.recording_received:
                # A report may have arrived before this override. Its audio is
                # no longer authoritative; preserve only its transcript.
                state.pending_audio = None
                state.recording_started_at = None
                state.audio_status = None
            self._refresh_state(state)

    def complete_recording(
        self,
        thread_id: str,
        data: Optional[bytes],
        *,
        name: str = "recording.ogg",
        mime_type: Optional[str] = None,
        started_at: Optional[float] = None,
    ) -> None:
        """Attach completed egress audio, or ``None`` for a terminal failure.

        ``data`` contains the completed recording bytes. ``name`` defaults to
        ``recording.ogg`` and ``mime_type`` defaults to the processor's configured
        audio MIME type. ``started_at`` is the epoch time of the recording's first
        sample and enables waterfall alignment.
        """
        pending_audio = None
        status: Optional[str] = "none"
        if data:
            if (
                self.audio_size_limit_bytes is not None
                and len(data) > self.audio_size_limit_bytes
            ):
                status = "too_large"
            else:
                pending_audio = _PendingAudio(
                    name=name,
                    data=bytes(data),
                    mime_type=mime_type or self._audio_mime_type,
                )
                status = None

        thread = str(thread_id)
        with self._state_lock:
            state = self._get_state_by_thread(thread)
            if state is None:
                if self._completed_threads.get(thread):
                    self._warn_missing_conversation(thread, "recording")
                    return
                pending = self._thread_state_waiting_for_trace.get(thread)
                if pending is None:
                    pending = _PendingThreadState()
                # A completed external recording is itself sufficient to
                # identify this thread's source as egress. ``expect_recording``
                # is still needed when the processor must wait before it arrives.
                pending.recording_mode = "egress"
                pending.pending_audio = pending_audio
                pending.recording_started_at = started_at
                pending.audio_status = status
                pending.recording_received = True
                self._thread_state_waiting_for_trace[thread] = pending
                return
            state.recording_mode = "egress"
            state.pending_audio = pending_audio
            state.recording_started_at = started_at
            state.audio_status = status
            state.recording_received = True
            self._refresh_state(state)
            trace_id = state.trace_id
        self._export_conversation_if_ready(trace_id)

    def _warn_missing_conversation(self, thread_id: str, delivery: str) -> None:
        logger.warning(
            "langsmith voice: no active LiveKit trace for thread %s; the %s "
            "arrived after export, or the id did not match set_thread_id().",
            thread_id,
            delivery,
        )

    def _audio_from_session_report(
        self, report: Any
    ) -> tuple[Optional[_PendingAudio], Optional[float], Optional[str]]:
        audio_path = getattr(report, "audio_recording_path", None)
        started_at = getattr(report, "audio_recording_started_at", None)
        if audio_path is None:
            return None, started_at, "none"
        audio_path = Path(audio_path)
        data, status = self._read_audio_file(audio_path)
        if data is None:
            return None, started_at, status
        return (
            _PendingAudio(
                name=audio_path.name,
                data=data,
                mime_type=self._audio_mime_type,
            ),
            started_at,
            status,
        )

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        trace_id = tspan.span.context.trace_id
        name = tspan.span.name

        if name == _STT_SPAN:
            self._handle_stt(tspan)
        elif name == _LLM_INFERENCE_SPAN:
            self._handle_llm_request(tspan)
        elif name in _LLM_WRAPPER_SPANS:
            tspan.set_kind("chain")
        elif name == _TTS_INFERENCE_SPAN:
            self._handle_tts(tspan)
        elif name in _TTS_WRAPPER_SPANS:
            tspan.set_kind("chain")
        elif name == _TURN_SPAN:
            self._handle_turn(tspan)
        elif name == _USER_SPEAKING_SPAN:
            return self._handle_user_speaking(tspan)
        elif name == _SESSION_SPAN:
            self._handle_session_end(tspan)
        elif name == "eou_detection":
            tspan.set_kind("chain")
        elif name == _TOOL_SPAN:
            self._handle_tool(tspan)
        elif name == _REALTIME_METRICS_SPAN:
            tspan.set_kind("llm")
        elif tspan.span.parent is None and is_livekit_span(tspan.span):
            # Only LiveKit parentless spans are conversation roots; other OTel
            # integrations may share this provider.
            self._handle_root(tspan, trace_id)
            return False
        return True

    def _handle_session_end(self, tspan: TranslatedSpan) -> None:
        trace_id = tspan.span.context.trace_id
        tspan.set_kind("chain")
        with self._state_lock:
            state = self._get_or_create_state(trace_id)
            state.session_ended = True
            held = state.spans_waiting_for_transcript
            state.spans_waiting_for_transcript = []
            state.transcripts_waiting_for_span = []
            self._refresh_state(state)
        for speaking_span in held:
            self._export(speaking_span)
        self._export_conversation_if_ready(trace_id)

    def _handle_stt(self, tspan: TranslatedSpan) -> None:
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

        usage = extract_llm_usage(tspan.attributes.get("lk.llm_metrics"))
        if usage:
            tspan.set_usage(**usage)

        tspan.events[:] = [
            e
            for e in tspan.events
            if e.name != _LLM_CHOICE_EVENT and e.name not in _LLM_EVENT_ROLES
        ]

    def _handle_tts(self, tspan: TranslatedSpan) -> None:
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
        with self._state_lock:
            state = self._get_or_create_state(trace_id)
            state.transcript.append((sort_key, message))
            self._refresh_state(state)

    def _handle_user_speaking(self, tspan: TranslatedSpan) -> bool:
        """Handle a ``user_speaking`` span — the realtime user turn.

        Deferred (``False``): stamp+export now if the transcript was already
        buffered, else hold it until one is fed (or flushed untouched at session
        end). Exported as-is (``True``) when there's no thread id to pair against.
        """
        tspan.set_kind("chain")
        with self._state_lock:
            state = self._get_or_create_state(tspan.span.context.trace_id)
            if state.thread_id is None:
                return True
            has_transcript = bool(state.transcripts_waiting_for_span)
            transcript = (
                state.transcripts_waiting_for_span.pop(0) if has_transcript else ""
            )
            if not has_transcript:
                state.spans_waiting_for_transcript.append(tspan)
            self._refresh_state(state)
        if has_transcript:
            self._apply_user_transcript(tspan, transcript)
            self._export(tspan)
            return False
        return False

    def _record_user_transcript(self, thread_id: str, transcript: str) -> None:
        """Pair a realtime transcript (from ``instrument_session``) with its span.

        Applies it to the oldest held ``user_speaking`` span for the thread, or
        buffers it if that span hasn't ended yet.
        """
        tid = str(thread_id)
        with self._state_lock:
            state = self._get_state_by_thread(tid)
            if state is None:
                waiting = self._transcripts_waiting_for_trace.get(tid) or []
                waiting.append(transcript)
                self._transcripts_waiting_for_trace[tid] = waiting
                return
            tspan = (
                state.spans_waiting_for_transcript.pop(0)
                if state.spans_waiting_for_transcript
                else None
            )
            if tspan is None:
                state.transcripts_waiting_for_span.append(transcript)
            self._refresh_state(state)
        if tspan is not None:
            self._apply_user_transcript(tspan, transcript)
            self._export(tspan)

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
            self._append_transcript(
                tspan.span.context.trace_id, msg, tspan.span.start_time
            )

    def _handle_tool(self, tspan: TranslatedSpan) -> None:
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

    def _handle_root(self, tspan: TranslatedSpan, trace_id: int) -> None:
        tspan.set_kind("chain")
        tspan.set_root_span(True)
        tspan.set_metadata("ls_modality", "audio")
        tspan.set_metadata("ls_integration", "livekit")
        tspan.set_metadata(
            "ls_integration_version", (get_package_version("livekit-agents") or "")
        )
        with self._state_lock:
            state = self._get_or_create_state(trace_id)
            state.root = tspan
            self._refresh_state(state)
            missing_egress_thread = (
                state.recording_mode == "egress" and state.thread_id is None
            )
        if missing_egress_thread:
            logger.warning(
                "langsmith voice: egress trace %x has no thread id; its recording "
                "cannot be delivered. Call set_thread_id() before the conversation "
                "starts, or choose a different recording mode.",
                trace_id,
            )
        self._export_conversation_if_ready(trace_id)

    def _export_conversation_if_ready(
        self, trace_id: int, *, force: bool = False
    ) -> None:
        """Export the deferred root once the required session data is ready.

        Every mode waits for the report. Egress additionally waits for
        :meth:`complete_recording`. ``force`` skips those gates at shutdown.
        """
        with self._export_lock:
            with self._state_lock:
                claimed = self._claim_conversation_for_export(trace_id, force=force)
            if claimed is None:
                return
            state, root = claimed
            self._export_completed_conversation(state, root)

    def _claim_conversation_for_export(
        self, trace_id: int, *, force: bool
    ) -> Optional[tuple[_ConversationState, TranslatedSpan]]:
        state = self._get_state(trace_id)
        if state is None or state.root is None:
            return None
        if not force and not state.session_ended:
            return None
        expects_session_data = not force and self._expects_session_data(state)
        if expects_session_data and not self._has_required_session_data(state):
            self._schedule_release_timeout(state)
            return None

        root = state.root
        self._cancel_release_timer(state)
        self._state_by_trace.pop(trace_id, None)
        if state.thread_id is not None:
            self._completed_threads[state.thread_id] = True
            self._trace_by_thread.pop(state.thread_id, None)
            self._transcripts_waiting_for_trace.pop(state.thread_id, None)
        self._forget_thread_id(trace_id)
        return state, root

    def _expects_session_data(self, state: _ConversationState) -> bool:
        """Whether this conversation has a viable session-data delivery route."""
        if state.recording_mode == "egress":
            # External recordings are routed by ``complete_recording(thread_id)``.
            return state.thread_id is not None
        # The automatic close hook captures this state's exact OTel trace id, so
        # session-report and no-audio modes do not require a LangSmith thread id.
        # A thread id also permits manual delivery through attach_session_report.
        return state.report_hook_session_id is not None or state.thread_id is not None

    def _has_required_session_data(self, state: _ConversationState) -> bool:
        return state.report_received and (
            state.recording_mode != "egress" or state.recording_received
        )

    def _export_completed_conversation(
        self, state: _ConversationState, root: TranslatedSpan
    ) -> None:
        for speaking_span in state.spans_waiting_for_transcript:
            self._export(speaking_span)
        self._render_conversation(root, state)
        attached = self._attach_pending_audio(root, state)
        if attached:
            self._stamp_recording_origin(root, state.recording_started_at)
        self._export(root)

    def _schedule_release_timeout(self, state: _ConversationState) -> None:
        if state.release_timer is not None:
            return
        timer = threading.Timer(
            self._recording_timeout_seconds,
            self._on_recording_timeout,
            (state.trace_id,),
        )
        timer.daemon = True
        state.release_timer = timer
        self._refresh_state(state)
        timer.start()

    def _on_recording_timeout(self, trace_id: int) -> None:
        with self._state_lock:
            state = self._get_state(trace_id)
            if state is None:
                return
            state.release_timer = None
            if self._has_required_session_data(state):
                return
            missing = ["session report"] if not state.report_received else []
            if state.recording_mode == "egress" and not state.recording_received:
                missing.append("egress recording")
            logger.warning(
                "langsmith voice: timed out waiting for %s for thread %s after "
                "%.1fs; exporting the trace with available session data.",
                " and ".join(missing),
                state.thread_id,
                self._recording_timeout_seconds,
            )
            if state.recording_mode != "none" and state.pending_audio is None:
                state.audio_status = "timeout"
            self._refresh_state(state)
        self._export_conversation_if_ready(trace_id, force=True)

    def _cancel_release_timer(self, state: _ConversationState) -> None:
        timer = state.release_timer
        state.release_timer = None
        if timer is not None:
            timer.cancel()

    def _stamp_recording_origin(
        self, tspan: TranslatedSpan, started_at: Optional[float]
    ) -> None:
        """Stamp where the recording sits on the trace's timeline, and why.

        LiveKit's recorder starts inside ``session.start()`` — after room
        connect and agent setup — so the recording's first sample is seconds
        later than the root span's start. Without the offset the trace audio
        player has to assume they coincide, and playback runs ahead of the
        waterfall by that gap.
        """
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
        self, tspan: TranslatedSpan, state: _ConversationState
    ) -> None:
        """Set the conversation transcript as the root's input.

        Prefers a session report's chat history — it is ordered by the messages'
        own timestamps and carries the tool calls — and falls back to the
        transcript assembled from spans when no report was supplied.
        """
        if state.report_transcript:
            tspan.set_messages(prompt=state.report_transcript)
            return
        if not state.transcript:
            return
        tspan.set_messages(
            prompt=[msg for _, msg in sorted(state.transcript, key=lambda e: e[0])]
        )

    def shutdown(self) -> None:
        """Force-export any still-held roots and user_speaking spans, then shut down.

        ``force_flush`` deliberately does not — a still-held root there is
        legitimately in progress, not a buffered export waiting to drain.
        """
        with self._export_lock:
            with self._state_lock:
                trace_ids = list(self._state_by_trace)
                for state in list(self._state_by_trace.values()):
                    self._cancel_release_timer(state)
            for trace_id in trace_ids:
                self._export_conversation_if_ready(trace_id, force=True)
            with self._state_lock:
                remaining = list(self._state_by_trace.values())
                self._state_by_trace.clear()
                self._trace_by_thread.clear()
                self._thread_state_waiting_for_trace.clear()
                self._completed_threads.clear()
                self._transcripts_waiting_for_trace.clear()
            for state in remaining:
                for speaking_span in state.spans_waiting_for_transcript:
                    self._export(speaking_span)
            super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force-flush the downstream — deferred root spans are NOT finalized."""
        return super().force_flush(timeout_millis)

    def _read_audio_file(self, path: Path) -> tuple[Optional[bytes], Optional[str]]:
        """Read a recording from disk, size-checked *before* it is loaded.

        Returns ``(bytes, None)`` or ``(None, reason)``. The size is
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
            return path.read_bytes(), None
        except Exception:
            logger.warning(
                "langsmith voice: failed reading the recording at %s.",
                path,
                exc_info=True,
            )
            return None, "unreadable"

    def _attach_pending_audio(
        self, tspan: TranslatedSpan, state: _ConversationState
    ) -> bool:
        pending = state.pending_audio
        attached = False
        status = state.audio_status
        if pending is not None:
            if not pending.data:
                status = "none"
            elif (
                self.audio_size_limit_bytes is not None
                and len(pending.data) > self.audio_size_limit_bytes
            ):
                status = "too_large"
            else:
                attached = self._attach_audio(
                    tspan,
                    name=pending.name,
                    data=pending.data,
                    mime_type=pending.mime_type,
                )
                status = "attached" if attached else "none"
        if status is not None:
            tspan.set_metadata("ls_audio_attach_status", status)
        return attached

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
                    if name not in tspan.attributes:
                        tspan.attributes[name] = val
                continue
            if flat_key in tspan.attributes:
                continue
            tspan.attributes[flat_key] = value

        provider = normalize_provider(
            tspan.attributes.get("gen_ai.provider.name")
        ) or normalize_provider(tspan.attributes.get("gen_ai.system"))
        tspan.set_provider(provider)

        if (
            "lk.realtime_model_metrics" in tspan.attributes
            and "langsmith.usage_metadata" not in tspan.attributes
        ):
            usage = extract_realtime_usage(
                tspan.attributes["lk.realtime_model_metrics"]
            )
            if usage:
                tspan.set_usage(**usage)
