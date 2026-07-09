"""OTel → LangSmith bridge for LiveKit Agents.

LangSmith's OTel ingester reads the ``gen_ai.*`` / ``langsmith.*`` namespaces;
LiveKit emits its data under a ``lk.*`` vendor prefix the ingester doesn't
recognize — so without translation, transcripts, TTS metrics, EOU
probabilities, latency numbers, etc. all evaporate at ingest. This
:class:`LiveKitLangSmithSpanProcessor` rewrites ``lk.*`` into the keys LangSmith
understands before each span is exported. It inherits the downstream wrapping,
exporter, ``thread_id`` stamping, and message helpers from
:class:`BaseLangSmithSpanProcessor`.

Generic to any LiveKit agent
----------------------------
The processor only reads LiveKit's own ``lk.*`` attributes and the span's
name/position — it carries no knowledge of what the LLM stage is. Two rules:

1. **Translate LiveKit spans from their own data.** Each known LiveKit span
   (``user_turn``, ``llm_request``, ``tts_*``, ``agent_turn``,
   ``function_tool``, …) is classified and rendered from the ``lk.*`` attributes
   and ``gen_ai.*`` span events LiveKit sets on it.
2. **Leave everything else untouched.** Any span that isn't a LiveKit span —
   e.g. a LangChain/LangGraph run riding the same OTel provider when
   ``LANGSMITH_TRACING_MODE=otel`` — already arrives in LangSmith's native
   shape, so it's exported verbatim.

Two translation layers for LiveKit spans
----------------------------------------
1. **Per-span classification** — set ``langsmith.span.kind`` and pull the
   conversation into ``gen_ai.prompt`` / ``gen_ai.completion``. The genuine
   inference nodes (STT ``user_turn``, ``llm_request``, ``tts_request``) are
   ``llm``-kind; the framework wrappers (``llm_node``, ``tts_node``, retry
   spans) are ``chain``.
2. **Blanket ``lk.*`` pass-through** — every ``lk.*`` scalar lands as
   ``langsmith.metadata.lk_<name>``, and JSON-object blobs are flattened so each
   metric is its own field. Per-stage latencies surface this way too.

The whole-conversation transcript on the root span is accumulated from the
per-turn ``agent_turn`` spans, and the call recording is attached to the root.

The per-context ``set_thread_id`` (opt-in) stamps ``langsmith.metadata.thread_id``
on every span. The call recording is embedded on the root as a LangSmith
attachment one of two ways:

* ``audio_path_provider`` — a local file whose bytes are read and embedded. This
  suits console/dev, where LiveKit writes ``audio.ogg`` under
  ``ctx.session_directory``. That directory is ephemeral in a deployed worker, so
  it is not a production path.
* :meth:`~LiveKitLangSmithSpanProcessor.expect_recording` /
  :meth:`~LiveKitLangSmithSpanProcessor.complete_recording` — the production
  path. `LiveKit Egress <https://docs.livekit.io/home/egress/overview/>`_ records
  the room to your own storage, but only finishes uploading *after* the call. So
  the host calls ``expect_recording`` at the start (we hold the root span open),
  then downloads the finished file and calls ``complete_recording`` with the
  bytes — embedded as a real attachment, just like the dev path.

With neither set, the processor needs nothing from the host app.
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Callable, Optional

from cachetools import TTLCache

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice.base_span_processor import (
    BaseLangSmithSpanProcessor,
    TranslatedSpan,
)

# Default lifetime (seconds) for the per-conversation state held between a
# trace's first and last span. The normal path frees it when the session ends
# (and shutdown/force_flush flushes any still-held root); the TTL bounds it for
# conversations that never end (crash, dropped connection) on a long-running
# worker. Generous enough to outlast a slow Egress upload.
DEFAULT_STATE_TTL_SECONDS = 3600.0

# Hard ceiling on tracked conversations, independent of the TTL — a backstop
# against a flood of new conversations within one TTL window (oldest evicted
# first). The TTL is the governing limit in practice.
DEFAULT_STATE_MAXSIZE = 100_000

# The instrumentation scope LiveKit's tracer is created under
# (``get_tracer("livekit-agents")``). Every span LiveKit emits carries it, so it
# is how we tell a LiveKit span apart from a non-LiveKit run riding the same OTel
# provider (e.g. a LangChain/LangGraph trace under ``LANGSMITH_TRACING_MODE=otel``).
_LIVEKIT_INSTRUMENTATION_SCOPE = "livekit-agents"

# LiveKit's span names, grouped by how we treat them. The genuine inference
# calls are ``llm``-kind; the framework wrappers around them are ``chain``.
_STT_SPAN = "user_turn"  # audio → transcript (inference)
_LLM_INFERENCE_SPAN = "llm_request"  # chat completion (inference)
_LLM_WRAPPER_SPANS = {"llm_node", "llm_request_run"}
_TTS_INFERENCE_SPAN = "tts_request"  # text → audio (inference)
_TTS_WRAPPER_SPANS = {"tts_node", "tts_request_run"}
_TURN_SPAN = "agent_turn"
_SESSION_SPAN = "agent_session"
_TOOL_SPAN = "function_tool"
_REALTIME_METRICS_SPAN = "realtime_metrics"

# LiveKit records each chat-context item sent to the model as a span event on
# ``llm_request`` (the event name implies the message role), followed by a
# ``gen_ai.choice`` event carrying the generated message.
_LLM_EVENT_ROLES = {
    "gen_ai.system.message": "system",
    "gen_ai.user.message": "user",
    "gen_ai.assistant.message": "assistant",
    "gen_ai.tool.message": "tool",
}
_LLM_CHOICE_EVENT = "gen_ai.choice"

# LiveKit reports some providers as the API base-URL host (e.g. its OpenAI
# plugin → ``api.openai.com``), but LangSmith's cost engine keys on provider
# *slugs* (``openai`` / ``deepgram`` / …), so a hostname never matches a price.
# We recover the slug by substring — so ``beta.anthropic.com`` still → ``anthropic``
# — mirroring how LangSmith itself infers the provider from a model name.
_PROVIDER_ALIASES = (
    "openai",
    "anthropic",
    "gemini",
    "google",
    "deepgram",
    "cartesia",
    "elevenlabs",
    "cohere",
    "mistral",
    "groq",
)


def _normalize_provider(raw: Any) -> Optional[str]:
    """Map a LiveKit provider (often an API host) to a LangSmith provider slug.

    Matches a known provider slug as a substring (so ``api.openai.com`` and
    ``beta.anthropic.com`` resolve to ``openai`` / ``anthropic``); otherwise
    returns the value's host, stripped of scheme/path. Returns ``None`` for
    empty input or LiveKit's ``"unknown"`` placeholder, so we never stamp a
    non-matching provider.
    """
    if not raw:
        return None
    value = str(raw).strip().lower()
    if not value or value == "unknown":
        return None
    for alias in _PROVIDER_ALIASES:
        if alias in value:
            return alias
    return value.split("://", 1)[-1].split("/", 1)[0] or None


class LiveKitLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches LiveKit Agents' OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[Any] = None,
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
            audio_path_provider: zero-arg callable returning a local recording
                path whose bytes are embedded in the root span; ``None`` disables.
                Console/dev only — see the module docstring. For production, use
                :meth:`expect_recording` / :meth:`complete_recording` to attach a
                LiveKit Egress recording.
            audio_mime_type: default MIME type for embedded recordings.
            state_ttl_seconds: lifetime for the per-conversation state held
                between a trace's first and last span; the backstop that frees
                state for conversations that never end (no ``agent_session`` span).
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

        # All per-conversation state is TTL-bounded so a conversation that never
        # ends (crash, dropped connection) can't leak it on a long-running
        # worker — the held root span and pending egress audio are the largest.
        # NB: ``TTLCache`` is not thread-safe; every cache here is mutated only
        # from the single LiveKit/asyncio event loop (``on_end`` and the host's
        # ``expect_recording`` / ``complete_recording`` calls all run there).
        def _cache() -> Any:
            return TTLCache(maxsize=DEFAULT_STATE_MAXSIZE, ttl=state_ttl_seconds)

        # Whole-conversation transcript, accumulated turn-by-turn from the
        # ``agent_turn`` spans. trace_id (int) -> flat [{role, content}, ...].
        self._conversation_by_trace: MutableMapping[int, list[dict]] = _cache()
        # The trace root (job entrypoint) ends before the conversation completes
        # when the agent greets first, so we hold its draft until ``agent_session``
        # ends with the full conversation. trace_id (hex str) -> TranslatedSpan.
        self._deferred_root_spans: MutableMapping[str, TranslatedSpan] = _cache()
        # Used as a set (trace_id -> True): sessions whose end span has arrived.
        self._ended_sessions: MutableMapping[str, bool] = _cache()
        # Production egress audio arrives *after* the call, so a conversation can
        # ask us to hold its root until ``complete_recording`` supplies the bytes.
        # Keyed by thread id (the conversation id the host controls);
        # ``_awaiting_recording`` is used as a set (thread_id -> True).
        self._awaiting_recording: MutableMapping[str, bool] = _cache()
        self._pending_audio: MutableMapping[str, dict] = _cache()
        self._thread_to_trace: MutableMapping[str, str] = _cache()
        self._trace_to_thread: MutableMapping[str, str] = _cache()
        # Realtime-model metrics cached from a ``realtime_metrics`` child span and
        # drained onto its parent ``agent_turn``. Keyed by the parent span_id.
        self._realtime_metrics_by_parent: MutableMapping[int, dict] = _cache()

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, tspan: TranslatedSpan) -> bool:
        trace_id = format(tspan.span.context.trace_id, "032x")
        name = tspan.span.name

        if name == _STT_SPAN:
            self._handle_stt(tspan)
        elif name == _LLM_INFERENCE_SPAN:
            self._handle_llm_request(tspan)
        elif name in _LLM_WRAPPER_SPANS:
            tspan.set_kind("chain")  # wrappers: no fabricated I/O
        elif name == _TTS_INFERENCE_SPAN or name in _TTS_WRAPPER_SPANS:
            self._handle_tts(tspan)
        elif name == _TURN_SPAN:
            self._handle_turn(tspan)
        elif name == _SESSION_SPAN:
            # Session end: the conversation is complete — release the deferred
            # root (if any), then export the session span itself.
            tspan.set_kind("chain")
            self._ended_sessions[trace_id] = True
            self._release_root_span(trace_id)
        elif name == "eou_detection":
            tspan.set_kind("chain")  # framework step
        elif name == _TOOL_SPAN:
            self._handle_tool(tspan)
        elif name == _REALTIME_METRICS_SPAN:
            # These belong ON the turn, not as their own span: cache for the
            # parent agent_turn and suppress this span entirely (False = the base
            # must not export it; nothing else does either).
            self._cache_realtime_metrics(tspan)
            return False
        elif tspan.span.parent is None and self._is_livekit_span(tspan.span):
            # The trace root (LiveKit's job entrypoint). _handle_root owns its
            # export: it renders/attaches and exports immediately, or defers
            # until the session ends and egress audio is ready (via
            # _maybe_release). Either way the base must not export it (False).
            #
            # Gated on the LiveKit scope so a *non-LiveKit* parentless span —
            # e.g. a LangChain/LangGraph root riding the same OTel provider — is
            # not mistaken for the conversation root, deferred, and mislabeled
            # ``langsmith.root_span``/``ls_modality=audio``; it falls through and
            # is exported untouched below.
            self._handle_root(tspan, trace_id)
            return False
        # Any other span isn't a LiveKit span (e.g. a LangChain/LangGraph run);
        # it already arrives in LangSmith's native shape — export untouched.
        #
        # Return True so the base exports this span once (the session span
        # included; _release_root_span above exports only the separate deferred
        # root, never this one).
        return True

    @staticmethod
    def _is_livekit_span(span: Any) -> bool:
        """Whether a span came from LiveKit's tracer (its instrumentation scope).

        Used to gate root detection: only a parentless span emitted by LiveKit is
        the conversation root. Named LiveKit spans are matched by name above and
        don't need this; it guards the broad ``parent is None`` case alone.
        """
        scope = getattr(span, "instrumentation_scope", None)
        return getattr(scope, "name", None) == _LIVEKIT_INSTRUMENTATION_SCOPE

    # -- per-span-type handlers ----------------------------------------------

    def _stamp_provider(self, tspan: TranslatedSpan, metrics_attr: str) -> None:
        """Normalize the provider to a LangSmith slug for a LiveKit span.

        LiveKit reports the provider as the API-base-URL host (its OpenAI plugin
        → ``api.openai.com``) and, depending on version, under either
        ``gen_ai.provider.name`` (livekit-agents ≥1.5) or ``gen_ai.system``.
        LangSmith ingestion maps either to ``ls_provider``, so we resolve a slug
        from the metric blob's ``metadata.model_provider`` or whichever key the
        span carries, then write it back to *both* keys. No-ops when no usable
        provider is available, rather than stamp ``"unknown"``.
        """
        provider = None
        metrics = self._try_parse_json_object(tspan.attributes.get(metrics_attr))
        if isinstance(metrics, dict):
            provider = (metrics.get("metadata") or {}).get("model_provider")
        provider = (
            _normalize_provider(provider)
            or _normalize_provider(tspan.attributes.get("gen_ai.provider.name"))
            or _normalize_provider(tspan.attributes.get("gen_ai.system"))
        )
        if provider:
            tspan.attributes["gen_ai.provider.name"] = provider
            tspan.attributes["gen_ai.system"] = provider

    def _handle_stt(self, tspan: TranslatedSpan) -> None:
        """STT (``user_turn``): audio input → transcribed text."""
        tspan.set_kind("llm")
        model = tspan.attributes.get("gen_ai.request.model")
        if model:
            tspan.attributes["langsmith.metadata.model_name"] = str(model)
        self._stamp_provider(tspan, "lk.stt_metrics")

        transcript = tspan.attributes.get("lk.user_transcript")
        tspan.set_messages(
            prompt=[{"role": "user", "content": f'Audio for: "{transcript}"'}]
        )
        if transcript:
            tspan.set_messages(
                completion=[{"role": "assistant", "content": str(transcript)}]
            )
        tspan.exclude_from_message_view()

    def _handle_llm_request(self, tspan: TranslatedSpan) -> None:
        """``llm_request``: the chat-completion call.

        LiveKit records the request's I/O as span events: one
        ``gen_ai.{system,user,assistant,tool}.message`` event per chat-context
        item, then a ``gen_ai.choice`` with the generated message. We rebuild
        ``gen_ai.prompt``/``gen_ai.completion`` (singular JSON, so tool calls
        survive) and strip the translated events so the ingester doesn't render
        them twice.
        """
        tspan.set_kind("llm")

        prompt: list[dict] = []
        completion: list[dict] = []
        for event in tspan.events:
            if event.name == _LLM_CHOICE_EVENT:
                completion.append(self._message_from_event("assistant", event))
            elif (role := _LLM_EVENT_ROLES.get(event.name)) is not None:
                prompt.append(self._message_from_event(role, event))
        tspan.set_messages(prompt=prompt or None, completion=completion or None)
        # Normalize the provider (LiveKit's OpenAI plugin reports the
        # ``api.openai.com`` host, which won't match a LangSmith price).
        self._stamp_provider(tspan, "lk.llm_metrics")

        # Drop the translated events (keep others, e.g. exceptions) on the
        # draft — finalize rebuilds the span from it, so span._events is left
        # untouched.
        tspan.events[:] = [
            e
            for e in tspan.events
            if e.name != _LLM_CHOICE_EVENT and e.name not in _LLM_EVENT_ROLES
        ]

    def _message_from_event(self, role: str, event: Any) -> dict:
        """Build a message dict from a LiveKit gen_ai event.

        Tool calls are forwarded in their OpenAI shape (parsing any JSON-string
        entries to objects) — LangSmith's ingester renders them directly.
        """
        attrs = event.attributes or {}
        msg: dict = {
            "role": str(attrs.get("role") or role),
            "content": str(attrs.get("content") or ""),
        }
        tool_calls = []
        for raw in attrs.get("tool_calls") or ():
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    continue
            if isinstance(raw, dict):
                tool_calls.append(raw)
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if role == "tool":
            if attrs.get("id"):
                msg["tool_call_id"] = str(attrs["id"])
            if attrs.get("name"):
                msg["name"] = str(attrs["name"])
        return msg

    def _handle_tts(self, tspan: TranslatedSpan) -> None:
        """Render the TTS spans.

        ``tts_request`` is the synthesis call (``llm``); the ``tts_node`` /
        ``tts_request_run`` wrappers are ``chain``s.
        """
        if tspan.span.name != _TTS_INFERENCE_SPAN:
            tspan.set_kind("chain")
            return

        tspan.set_kind("llm")
        tspan.exclude_from_message_view()

        text = (
            tspan.attributes.get("lk.input_text")
            or tspan.attributes.get("lk.request.text")
            or tspan.attributes.get("lk.text")
            or ""
        )
        tspan.set_messages(
            prompt=[{"role": "user", "content": str(text)}],
            completion=[
                {"role": "assistant", "content": f'Generated audio for: "{text}"'}
            ],
        )

        model = tspan.attributes.get("gen_ai.request.model")
        if not model:
            metrics = self._try_parse_json_object(
                tspan.attributes.get("lk.tts_metrics")
            )
            if isinstance(metrics, dict):
                model = (metrics.get("metadata") or {}).get(
                    "model_name"
                ) or metrics.get("model_name")
        if model:
            tspan.attributes["gen_ai.request.model"] = str(model)
            tspan.attributes["langsmith.metadata.model_name"] = str(model)
        self._stamp_provider(tspan, "lk.tts_metrics")

    def _handle_turn(self, tspan: TranslatedSpan) -> None:
        """Render an ``agent_turn``: one user/assistant exchange.

        Appends the exchange to the running conversation the root rolls up. This
        is the LiveKit-native turn boundary, so it works for both the cascade and
        the speech-to-speech backends.
        """
        tspan.set_kind("chain")
        self._drain_realtime_metrics(tspan)

        user_input = tspan.attributes.get("lk.user_input")
        response = tspan.attributes.get("lk.response.text")
        trace_id = tspan.span.context.trace_id
        conversation = self._conversation_by_trace.get(trace_id) or []
        if user_input:
            msg = {"role": "user", "content": str(user_input)}
            tspan.set_messages(prompt=[msg])
            conversation.append(msg)
        if response:
            msg = {"role": "assistant", "content": str(response)}
            tspan.set_messages(completion=[msg])
            conversation.append(msg)
        # Re-assign (not just mutate) so each turn refreshes the TTL — an active
        # call longer than the TTL is never evicted mid-conversation.
        if conversation:
            self._conversation_by_trace[trace_id] = conversation

    def _handle_tool(self, tspan: TranslatedSpan) -> None:
        """``function_tool``: render as a proper ``tool`` run with its I/O."""
        tspan.set_kind("tool")
        tool_name = tspan.attributes.get("lk.function_tool.name")
        if tool_name:
            tspan.attributes["langsmith.metadata.tool_name"] = str(tool_name)
        args = tspan.attributes.get("lk.function_tool.arguments")
        if args is not None:
            tspan.attributes["gen_ai.prompt"] = (
                args if isinstance(args, str) else json.dumps(args)
            )
        output = tspan.attributes.get("lk.function_tool.output")
        if output is not None:
            tspan.attributes["gen_ai.completion"] = (
                output if isinstance(output, str) else json.dumps(output)
            )

    # -- production recording (egress) ---------------------------------------

    def expect_recording(self, thread_id: str) -> None:
        """Hold this conversation's root span until its recording is supplied.

        LiveKit Egress finishes uploading *after* the call ends, so the bytes
        don't exist when the root span would normally be exported. Call this at
        the start of a conversation (when you start egress) to defer that export;
        then call :meth:`complete_recording` once you have the file. Until then
        the root is held (a worker shutdown flushes it without audio as a
        fallback), so always pair this with a ``complete_recording`` call —
        passing ``None`` to release without audio if the recording fails.

        Args:
            thread_id: the conversation id, matching the one passed to
                ``set_thread_id``.
        """
        self._awaiting_recording[str(thread_id)] = True

    def complete_recording(
        self,
        thread_id: str,
        data: Optional[bytes],
        *,
        name: str = "recording.ogg",
        mime_type: Optional[str] = None,
    ) -> None:
        """Attach an egress recording to a conversation and release its root.

        Download the completed egress file from your storage and pass its bytes
        here; they're embedded as a real LangSmith attachment on the root span.
        Pass ``data=None`` to release the held root without audio (e.g. egress
        failed). Safe to call before or after the session ends.

        Args:
            thread_id: the conversation id, matching :meth:`expect_recording`.
            data: the recording bytes, or ``None`` to release without audio.
            name: attachment filename.
            mime_type: attachment MIME type; defaults to the processor's.
        """
        tid = str(thread_id)
        if data:
            self._pending_audio[tid] = {
                "name": name,
                "data": bytes(data),
                "mime_type": mime_type or self._audio_mime_type,
            }
        self._awaiting_recording.pop(tid, None)
        trace_id = self._thread_to_trace.get(tid)
        if trace_id is not None:
            self._maybe_release(trace_id)

    # -- deferred root release ------------------------------------------------

    def _handle_root(self, tspan: TranslatedSpan, trace_id: str) -> None:
        """Handle the trace root (job entrypoint), the conversation root.

        The root ends before the conversation completes (the agent greets first),
        so we always defer it and release it — complete, with audio — once the
        session has ended and any awaited recording has arrived.
        """
        tspan.set_kind("chain")
        tspan.set_root_span(True)
        tspan.set_metadata("ls_modality", "audio")
        tspan.set_metadata("ls_integration", "livekit")
        tspan.set_metadata(
            "ls_integration_version", (get_package_version("livekit-agents") or "")
        )

        thread = tspan.attributes.get("langsmith.metadata.thread_id")
        if thread is not None:
            self._thread_to_trace[str(thread)] = trace_id
            self._trace_to_thread[trace_id] = str(thread)

        self._deferred_root_spans[trace_id] = tspan
        self._maybe_release(trace_id)

    def _release_root_span(self, trace_id: str) -> None:
        """Session ended: release the root if ready (see :meth:`_maybe_release`)."""
        self._maybe_release(trace_id)

    def _maybe_release(self, trace_id: str) -> None:
        """Export the deferred root once the session ended and audio is ready.

        Three conditions must hold: the root span has been seen, the
        ``agent_session`` has ended, and the conversation isn't still awaiting an
        egress recording. Any of the three call sites (root seen, session end,
        ``complete_recording``) can be the one that satisfies the last condition.
        """
        tspan = self._deferred_root_spans.get(trace_id)
        if tspan is None or trace_id not in self._ended_sessions:
            return
        thread = self._trace_to_thread.get(trace_id)
        if thread is not None and thread in self._awaiting_recording:
            return  # still waiting for complete_recording()

        self._deferred_root_spans.pop(trace_id, None)
        self._render_conversation(tspan)
        self._attach_audio_recording(tspan)
        if thread is not None:
            self._attach_pending_audio(tspan, thread)
        self._export(tspan)
        self._cleanup_trace(trace_id)

    def _render_conversation(self, tspan: TranslatedSpan) -> bool:
        """Render the accumulated conversation onto a root span.

        Input = the opening message; output = everything after it. Returns
        whether anything was rendered.
        """
        messages = self._conversation_by_trace.get(tspan.span.context.trace_id, [])
        if not messages:
            return False
        tspan.set_messages(prompt=messages[:1])
        if len(messages) > 1:
            tspan.set_messages(completion=messages[1:])
        return True

    def _cleanup_trace(self, trace_id: str) -> None:
        self._conversation_by_trace.pop(int(trace_id, 16), None)
        self._forget_thread_id(int(trace_id, 16))
        self._ended_sessions.pop(trace_id, None)
        thread = self._trace_to_thread.pop(trace_id, None)
        if thread is not None:
            self._thread_to_trace.pop(thread, None)
            self._awaiting_recording.pop(thread, None)
            self._pending_audio.pop(thread, None)

    def shutdown(self) -> None:
        """Flush any deferred root spans, then shut down the downstream."""
        self._flush_deferred_root_spans()
        super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force-flush the downstream — deferred root spans are NOT finalized.

        Unlike ``shutdown``, ``force_flush`` can fire *mid-conversation* (a
        periodic flush, or any ``provider.force_flush()`` caller). A deferred root
        is still being assembled — its ``agent_session`` hasn't ended — so
        finalizing and exporting it here would emit a partial root and drop it,
        losing the real root when the session later ends. So in-progress roots are
        left held; only ``shutdown`` (terminal) flushes them as a last resort.
        """
        return super().force_flush(timeout_millis)

    def _flush_deferred_root_spans(self) -> None:
        """Export any root spans still held — last resort, ``shutdown`` only.

        Covers a session that ended abnormally, or an awaited recording that
        never arrived before shutdown. Not called from ``force_flush``: a still-held
        root is legitimately in progress, not a buffered export waiting to drain.
        """
        for trace_id, tspan in list(self._deferred_root_spans.items()):
            if not self._render_conversation(tspan):
                tspan.set_messages(
                    prompt=[{"role": "system", "content": "Conversation not captured"}],
                    completion=[
                        {
                            "role": "assistant",
                            "content": "No conversation turns recorded.",
                        }
                    ],
                )
            self._attach_audio_recording(tspan)
            thread = self._trace_to_thread.get(trace_id)
            if thread is not None:
                self._attach_pending_audio(tspan, thread)
            self._export(tspan)
            del self._deferred_root_spans[trace_id]

    # -- audio attachment -----------------------------------------------------

    def _attach_audio_recording(self, tspan: TranslatedSpan) -> None:
        if self.audio_path_provider is None:
            return
        audio_path = self.audio_path_provider()
        if audio_path is None:
            return
        try:
            if not audio_path.exists():
                return
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
        pending = self._pending_audio.pop(thread, None)
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
        parent_id = tspan.span.parent.span_id if tspan.span.parent else None
        if parent_id is None:
            return
        cached = {
            k: v
            for k, v in tspan.attributes.items()
            if k.startswith("lk.") or k.startswith("gen_ai.usage")
        }
        # Lift token counts into gen_ai.usage.* for cost tracking.
        metrics = self._try_parse_json_object(
            tspan.attributes.get("lk.realtime_model_metrics")
        )
        if isinstance(metrics, dict):
            for src, dst in (
                ("input_tokens", "gen_ai.usage.input_tokens"),
                ("output_tokens", "gen_ai.usage.output_tokens"),
                ("total_tokens", "gen_ai.usage.total_tokens"),
            ):
                v = metrics.get(src)
                if isinstance(v, (int, float)):
                    cached[dst] = v
        if cached:
            self._realtime_metrics_by_parent[parent_id] = cached

    def _drain_realtime_metrics(self, tspan: TranslatedSpan) -> None:
        """Copy cached realtime metrics onto this (agent_turn) span (if absent)."""
        cached = self._realtime_metrics_by_parent.pop(tspan.span.context.span_id, None)
        if not cached:
            return
        for k, v in cached.items():
            if k not in tspan.attributes:
                tspan.attributes[k] = v

    # -- blanket lk.* pass-through (runs just before export) ------------------

    def _pre_export(self, tspan: TranslatedSpan) -> None:
        """Forward every ``lk.*`` attribute to ``langsmith.metadata.lk_<name>``.

        Scalars and sequences of scalars are forwarded directly; JSON-object
        blobs are flattened so each metric is its own field.
        """
        for key in list(tspan.attributes.keys()):
            if not key.startswith("lk."):
                continue
            v = tspan.attributes[key]
            if v is None or isinstance(v, dict):
                continue
            ms_key = f"langsmith.metadata.{key.replace('.', '_')}"
            parsed = self._try_parse_json_object(v)
            if parsed is not None:
                self._flatten_into_metadata(tspan, ms_key, parsed)
                continue
            if ms_key in tspan.attributes:  # don't clobber what a branch set
                continue
            tspan.attributes[ms_key] = v

        # Normalize the provider to a LangSmith slug on EVERY exported span,
        # under both keys LiveKit/LangSmith use across versions —
        # ``gen_ai.provider.name`` (livekit-agents ≥1.5) and the legacy
        # ``gen_ai.system`` — so ``api.openai.com`` → ``openai`` regardless of
        # which one carries it. Done at the single export chokepoint so it also
        # catches spans that never reach the per-stage handlers.
        for key in ("gen_ai.provider.name", "gen_ai.system"):
            normalized = _normalize_provider(tspan.attributes.get(key))
            if normalized:
                tspan.attributes[key] = normalized

    @staticmethod
    def _try_parse_json_object(value: Any) -> Optional[dict]:
        """Return ``value`` parsed as a dict if it's a JSON-object string, else None."""
        if not isinstance(value, str):
            return None
        s = value.strip()
        if not (s.startswith("{") and s.endswith("}")):
            return None
        try:
            obj = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None
        return obj if isinstance(obj, dict) else None

    def _flatten_into_metadata(
        self, tspan: TranslatedSpan, prefix: str, obj: dict, _depth: int = 0
    ) -> None:
        """Flatten a dict's scalar leaves to ``langsmith.metadata.<prefix>_<key>``."""
        if _depth > 4:
            return
        for k, v in obj.items():
            name = f"{prefix}_{k}"
            if isinstance(v, dict):
                self._flatten_into_metadata(tspan, name, v, _depth + 1)
            elif isinstance(v, (str, int, float, bool)):
                if name not in tspan.attributes:
                    tspan.attributes[name] = v
            elif (
                isinstance(v, (list, tuple))
                and v
                and all(isinstance(item, (str, int, float, bool)) for item in v)
            ):
                if name not in tspan.attributes:
                    tspan.attributes[name] = list(v)
