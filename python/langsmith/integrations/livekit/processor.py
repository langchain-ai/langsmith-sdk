"""OTel → LangSmith bridge for LiveKit Agents.

Rewrites LiveKit's ``lk.*`` span data into the ``gen_ai.*`` / ``langsmith.*``
namespaces LangSmith ingests; non-LiveKit spans on the same provider pass
through untouched. The call recording is attached to the root span, either from
a local file (``audio_path_provider``, dev) or via :meth:`expect_recording` /
:meth:`complete_recording` (LiveKit Egress, production). Shared export /
``thread_id`` / message plumbing lives in :class:`BaseLangSmithSpanProcessor`.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Callable, Optional

from cachetools import TTLCache
from opentelemetry.sdk.trace import SpanProcessor

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice.base_span_processor import (
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)

from ._helpers import (
    build_assistant_message,
    build_message_from_event,
    build_user_message,
    extract_model_from_lk_metrics,
    extract_provider_from_lk_metrics,
    flatten_lk_attributes_to_ls_metadata,
    is_livekit_span,
    normalize_provider,
    try_parse_json_object,
)

# Lifetime / cap for per-conversation state; bounds memory for calls that never end.
DEFAULT_STATE_TTL_SECONDS = 3600.0
DEFAULT_STATE_MAXSIZE = 100_000

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

# ``llm_request`` emits one ``gen_ai.<role>.message`` event per chat item, plus a
# ``gen_ai.choice`` for the reply.
_LLM_EVENT_ROLES = {
    "gen_ai.system.message": "system",
    "gen_ai.user.message": "user",
    "gen_ai.assistant.message": "assistant",
    "gen_ai.tool.message": "tool",
}
_LLM_CHOICE_EVENT = "gen_ai.choice"


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
        state_ttl_seconds: float = DEFAULT_STATE_TTL_SECONDS,
        **kwargs: Any,
    ) -> None:
        """Create the processor.

        Args:
            audio_path_provider: returns a local recording path to embed on the
                root (dev only); for production use :meth:`expect_recording` /
                :meth:`complete_recording`.
            audio_mime_type: default MIME type for embedded recordings.
            state_ttl_seconds: lifetime for per-conversation state.
        """
        super().__init__(
            downstream_processor,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
            **kwargs,
        )
        self.audio_path_provider = audio_path_provider
        self._audio_mime_type = audio_mime_type

        def _cache() -> Any:
            return TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)

        # trace_id -> running transcript, rolled up onto the root at session end.
        self._transcript_by_trace: MutableMapping[int, list[dict]] = _cache()
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
        # parent span_id -> realtime metrics to drain onto its ``agent_turn``.
        self._realtime_metrics_by_parent_span: MutableMapping[int, dict] = _cache()

    def _remember_thread_id(self, trace_id: int, thread_id: str) -> None:
        """Also index thread→trace (so ``complete_recording`` can find the trace)."""
        super()._remember_thread_id(trace_id, thread_id)
        self._trace_by_thread[thread_id] = trace_id

    # -- production recording (egress) ---------------------------------------

    def expect_recording(self, thread_id: str) -> None:
        """Hold the root span open until :meth:`complete_recording` supplies the audio.

        Call at conversation start (with egress); always pair with a
        ``complete_recording`` call. ``thread_id`` must match ``set_thread_id``.
        """
        self._threads_awaiting_recording[str(thread_id)] = True

    def complete_recording(
        self,
        thread_id: str,
        data: Optional[bytes],
        *,
        name: str = "recording.ogg",
        mime_type: Optional[str] = None,
    ) -> None:
        """Attach an egress recording and release the held root.

        ``data`` is the recording bytes (embedded as an attachment), or ``None``
        to release without audio. ``thread_id`` must match :meth:`expect_recording`.
        Safe to call before or after the session ends.
        """
        if data:
            self._pending_audio_by_thread[str(thread_id)] = {
                "name": name,
                "data": bytes(data),
                "mime_type": mime_type or self._audio_mime_type,
            }
        self._threads_awaiting_recording.pop(str(thread_id), None)
        trace_id = self._trace_by_thread.get(str(thread_id))
        if trace_id is not None:
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
        elif name == _SESSION_SPAN:
            # Session end: release the deferred root, then export this span.
            tspan.set_kind("chain")
            self._ended_session_traces[trace_id] = True
            self._maybe_release(trace_id)
        elif name == "eou_detection":
            tspan.set_kind("chain")  # framework step
        elif name == _TOOL_SPAN:
            self._handle_tool(tspan)
        elif name == _REALTIME_METRICS_SPAN:
            # Drained onto the parent agent_turn; suppress this span (False).
            self._cache_realtime_metrics(tspan)
            return False
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
        tspan.set_model(
            tspan.attributes.get("gen_ai.request.model")
            or extract_model_from_lk_metrics(tspan.attributes.get("lk.stt_metrics"))
        )
        provider = extract_provider_from_lk_metrics(
            tspan.attributes.get("lk.stt_metrics")
        )
        tspan.set_provider(normalize_provider(provider))

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
        """Render an ``agent_turn`` and append it to the running transcript."""
        tspan.set_kind("chain")
        self._drain_realtime_metrics(tspan)

        user_input = tspan.attributes.get("lk.user_input")
        response = tspan.attributes.get("lk.response.text")
        trace_id = tspan.span.context.trace_id
        conversation = self._transcript_by_trace.get(trace_id) or []
        if user_input:
            msg = build_user_message(str(user_input))
            tspan.set_messages(prompt=[msg])
            conversation.append(msg)
        if response:
            msg = build_assistant_message(str(response))
            tspan.set_messages(completion=[msg])
            conversation.append(msg)
        # Re-assign (not just mutate) so each turn refreshes the cache TTL.
        if conversation:
            self._transcript_by_trace[trace_id] = conversation

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
        ``force`` skips the last two gates — the last-resort path at
        :meth:`shutdown` for a root that never completed.
        """
        tspan = self._deferred_root_by_trace.get(trace_id)
        if tspan is None:
            return
        thread = self._thread_id_by_trace.get(trace_id)
        if not force:
            if trace_id not in self._ended_session_traces:
                return
            if thread is not None and thread in self._threads_awaiting_recording:
                return  # still waiting for complete_recording()

        self._deferred_root_by_trace.pop(trace_id, None)
        self._render_conversation(tspan)
        self._attach_audio_recording(tspan)
        if thread is not None:
            self._attach_pending_audio(tspan, thread)
        self._export(tspan)
        self._cleanup_trace(trace_id)

    def _render_conversation(self, tspan: TranslatedSpan) -> bool:
        """Set the whole transcript as the root's input messages; return if any."""
        messages = self._transcript_by_trace.get(tspan.span.context.trace_id, [])
        if not messages:
            return False
        tspan.set_messages(prompt=messages)
        return True

    def _cleanup_trace(self, trace_id: int) -> None:
        # Read the thread id before ``_forget_thread_id`` drops it from the base map.
        thread = self._thread_id_by_trace.get(trace_id)
        self._transcript_by_trace.pop(trace_id, None)
        self._forget_thread_id(trace_id)
        self._ended_session_traces.pop(trace_id, None)
        if thread is not None:
            self._trace_by_thread.pop(thread, None)
            self._threads_awaiting_recording.pop(thread, None)
            self._pending_audio_by_thread.pop(thread, None)

    def shutdown(self) -> None:
        """Force-export any still-held roots (last resort), then shut down.

        ``force_flush`` deliberately does not — a still-held root there is
        legitimately in progress, not a buffered export waiting to drain.
        """
        for trace_id in list(self._deferred_root_by_trace):
            self._maybe_release(trace_id, force=True)
        super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force-flush the downstream — deferred root spans are NOT finalized."""
        return super().force_flush(timeout_millis)

    # -- audio attachment -----------------------------------------------------

    def _attach_audio_recording(self, tspan: TranslatedSpan) -> None:
        """Embed audio from the local ``audio_path_provider`` file (dev)."""
        if self.audio_path_provider is None:
            return
        audio_path = self.audio_path_provider()
        if audio_path is None or not audio_path.exists():
            return
        try:
            audio_bytes = audio_path.read_bytes()
        except Exception:  # pragma: no cover
            return
        self._attach_audio(
            tspan,
            name=audio_path.name,
            data=audio_bytes,
            mime_type=self._audio_mime_type,
        )

    def _attach_pending_audio(self, tspan: TranslatedSpan, thread: str) -> None:
        """Embed a recording supplied via :meth:`complete_recording` (egress)."""
        pending = self._pending_audio_by_thread.pop(thread, None)
        if not pending or not pending.get("data"):
            return
        self._attach_audio(
            tspan,
            name=pending["name"],
            data=pending["data"],
            mime_type=pending["mime_type"],
        )

    # -- realtime-model metrics ----------------------------------------------

    def _cache_realtime_metrics(self, tspan: TranslatedSpan) -> None:
        """Stash a ``realtime_metrics`` span's data for its parent ``agent_turn``."""
        parent = tspan.span.parent
        if parent is None:
            return
        carried_metrics = {
            key: value
            for key, value in tspan.attributes.items()
            if key.startswith("lk.") or key.startswith("gen_ai.usage")
        }
        # Lift token counts into gen_ai.usage.* for cost tracking.
        model_metrics = try_parse_json_object(
            tspan.attributes.get("lk.realtime_model_metrics")
        )
        if isinstance(model_metrics, dict):
            for token_key in ("input_tokens", "output_tokens", "total_tokens"):
                count = model_metrics.get(token_key)
                if isinstance(count, (int, float)):
                    carried_metrics[f"gen_ai.usage.{token_key}"] = count
        if carried_metrics:
            self._realtime_metrics_by_parent_span[parent.span_id] = carried_metrics

    def _drain_realtime_metrics(self, tspan: TranslatedSpan) -> None:
        """Copy cached realtime metrics onto this ``agent_turn`` (never clobbering)."""
        carried_metrics = self._realtime_metrics_by_parent_span.pop(
            tspan.span.context.span_id, None
        )
        if not carried_metrics:
            return
        for key, value in carried_metrics.items():
            if key not in tspan.attributes:
                tspan.attributes[key] = value

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
