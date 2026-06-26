"""OTel → LangSmith bridge for LiveKit Agents.

LangSmith's OTel ingester reads the ``gen_ai.*`` / ``langsmith.*`` namespaces;
LiveKit emits its data under a ``lk.*`` vendor prefix the ingester doesn't
recognize — so without translation, transcripts, TTS metrics, EOU
probabilities, latency numbers, etc. all evaporate at ingest. This
:class:`LiveKitLangSmithSpanProcessor` rewrites ``lk.*`` into the keys LangSmith
understands before each span is exported. It inherits the downstream wrapping,
exporter, ``thread_id`` injection, and message helpers from
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

``thread_id_provider`` (opt-in) stamps ``langsmith.metadata.thread_id`` on every
span. The call recording is embedded on the root as a LangSmith attachment one
of two ways:

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
from pathlib import Path
from typing import Any, Callable, Optional

from opentelemetry.sdk.trace import ReadableSpan

from .._voice.base import BaseLangSmithSpanProcessor

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


class LiveKitLangSmithSpanProcessor(BaseLangSmithSpanProcessor):
    """Enriches LiveKit Agents' OTel spans with LangSmith-compatible attributes."""

    def __init__(
        self,
        downstream_processor: Optional[Any] = None,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        endpoint: Optional[str] = None,
        thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
        audio_path_provider: Optional[Callable[[], Optional[Path]]] = None,
        audio_mime_type: str = "audio/ogg",
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
        self.audio_path_provider = audio_path_provider
        self._audio_mime_type = audio_mime_type
        # Whole-conversation transcript, accumulated turn-by-turn from the
        # ``agent_turn`` spans. trace_id (int) -> flat [{role, content}, ...].
        self._conversation_by_trace: dict[int, list[dict]] = {}
        # The trace root (job entrypoint) ends before the conversation completes
        # when the agent greets first, so we hold it until ``agent_session`` ends
        # with the full conversation. trace_id (hex str) -> ReadableSpan.
        self._deferred_root_spans: dict[str, ReadableSpan] = {}
        self._ended_sessions: set[str] = set()
        # Production egress audio arrives *after* the call, so a conversation can
        # ask us to hold its root until ``complete_recording`` supplies the bytes.
        # All keyed by thread id (the conversation id the host controls).
        self._awaiting_recording: set[str] = set()
        self._pending_audio: dict[str, dict] = {}
        self._thread_to_trace: dict[str, str] = {}
        self._trace_to_thread: dict[str, str] = {}
        # Realtime-model metrics cached from a ``realtime_metrics`` child span and
        # drained onto its parent ``agent_turn``. Keyed by the parent span_id.
        self._realtime_metrics_by_parent: dict[int, dict] = {}

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, span: ReadableSpan) -> None:
        trace_id = format(span.context.trace_id, "032x")
        name = span.name

        if name == _STT_SPAN:
            self._handle_stt(span)
        elif name == _LLM_INFERENCE_SPAN:
            self._handle_llm_request(span)
        elif name in _LLM_WRAPPER_SPANS:
            self._set_kind(span, "chain")  # wrappers: no fabricated I/O
        elif name == _TTS_INFERENCE_SPAN or name in _TTS_WRAPPER_SPANS:
            self._handle_tts(span)
        elif name == _TURN_SPAN:
            self._handle_turn(span)
        elif name == _SESSION_SPAN:
            # Session end: the conversation is complete — release the deferred
            # root (if any), then export the session span itself.
            self._set_kind(span, "chain")
            self._ended_sessions.add(trace_id)
            self._release_root_span(trace_id)
        elif name == "eou_detection":
            self._set_kind(span, "chain")  # framework step
        elif name == _TOOL_SPAN:
            self._handle_tool(span)
        elif name == _REALTIME_METRICS_SPAN:
            # These belong ON the turn, not as their own span: cache for the
            # parent agent_turn and suppress this span entirely.
            self._cache_realtime_metrics(span)
            return
        elif span.parent is None:
            # The trace root (LiveKit's job entrypoint). Render, attach, export —
            # or defer if the conversation hasn't started yet.
            self._handle_root(span, trace_id)
            return
        # Any other span isn't a LiveKit span (e.g. a LangChain/LangGraph run);
        # it already arrives in LangSmith's native shape — export untouched.

        self._export(span)

    # -- per-span-type handlers ----------------------------------------------

    def _handle_stt(self, span: ReadableSpan) -> None:
        """STT (``user_turn``): audio input → transcribed text."""
        self._set_kind(span, "llm")
        model = span.attributes.get("gen_ai.request.model")
        if model:
            span._attributes["langsmith.metadata.model_name"] = str(model)

        transcript = span.attributes.get("lk.user_transcript")
        self._set_messages(
            span, prompt=[{"role": "user", "content": f'Audio for: "{transcript}"'}]
        )
        if transcript:
            self._set_messages(
                span, completion=[{"role": "assistant", "content": str(transcript)}]
            )
        self._exclude_from_message_view(span)

    def _handle_llm_request(self, span: ReadableSpan) -> None:
        """``llm_request``: the chat-completion call.

        LiveKit records the request's I/O as span events: one
        ``gen_ai.{system,user,assistant,tool}.message`` event per chat-context
        item, then a ``gen_ai.choice`` with the generated message. We rebuild
        ``gen_ai.prompt``/``gen_ai.completion`` (singular JSON, so tool calls
        survive) and strip the translated events so the ingester doesn't render
        them twice.
        """
        self._set_kind(span, "llm")

        prompt: list[dict] = []
        completion: list[dict] = []
        for event in span.events:
            if event.name == _LLM_CHOICE_EVENT:
                completion.append(self._message_from_event("assistant", event))
            elif (role := _LLM_EVENT_ROLES.get(event.name)) is not None:
                prompt.append(self._message_from_event(role, event))
        self._set_messages_json(
            span, prompt=prompt or None, completion=completion or None
        )

        # Drop the translated events (keep others, e.g. exceptions).
        span._events = [
            e
            for e in span.events
            if e.name != _LLM_CHOICE_EVENT and e.name not in _LLM_EVENT_ROLES
        ]

    def _message_from_event(self, role: str, event: Any) -> dict:
        """Build a LangChain-format message dict from a LiveKit gen_ai event."""
        attrs = event.attributes or {}
        msg: dict = {
            "role": str(attrs.get("role") or role),
            "content": str(attrs.get("content") or ""),
        }
        tool_calls = [
            tc
            for raw in (attrs.get("tool_calls") or ())
            if (tc := self._flatten_tool_call(raw)) is not None
        ]
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if role == "tool":
            if attrs.get("id"):
                msg["tool_call_id"] = str(attrs["id"])
            if attrs.get("name"):
                msg["name"] = str(attrs["name"])
        return msg

    def _handle_tts(self, span: ReadableSpan) -> None:
        """Render the TTS spans.

        ``tts_request`` is the synthesis call (``llm``); the ``tts_node`` /
        ``tts_request_run`` wrappers are ``chain``s.
        """
        if span.name != _TTS_INFERENCE_SPAN:
            self._set_kind(span, "chain")
            return

        self._set_kind(span, "llm")
        self._exclude_from_message_view(span)

        text = (
            span.attributes.get("lk.input_text")
            or span.attributes.get("lk.request.text")
            or span.attributes.get("lk.text")
            or ""
        )
        self._set_messages(
            span,
            prompt=[{"role": "user", "content": str(text)}],
            completion=[
                {"role": "assistant", "content": f'Generated audio for: "{text}"'}
            ],
        )

        model = span.attributes.get("gen_ai.request.model")
        if not model:
            metrics = self._try_parse_json_object(span.attributes.get("lk.tts_metrics"))
            if isinstance(metrics, dict):
                model = (metrics.get("metadata") or {}).get(
                    "model_name"
                ) or metrics.get("model_name")
        if model:
            span._attributes["gen_ai.request.model"] = str(model)
            span._attributes["langsmith.metadata.model_name"] = str(model)

    def _handle_turn(self, span: ReadableSpan) -> None:
        """Render an ``agent_turn``: one user/assistant exchange.

        Appends the exchange to the running conversation the root rolls up. This
        is the LiveKit-native turn boundary, so it works for both the cascade and
        the speech-to-speech backends.
        """
        self._set_kind(span, "chain")
        self._drain_realtime_metrics(span)

        user_input = span.attributes.get("lk.user_input")
        response = span.attributes.get("lk.response.text")
        conversation = self._conversation_by_trace.setdefault(span.context.trace_id, [])
        if user_input:
            msg = {"role": "user", "content": str(user_input)}
            self._set_messages(span, prompt=[msg])
            conversation.append(msg)
        if response:
            msg = {"role": "assistant", "content": str(response)}
            self._set_messages(span, completion=[msg])
            conversation.append(msg)

    def _handle_tool(self, span: ReadableSpan) -> None:
        """``function_tool``: render as a proper ``tool`` run with its I/O."""
        self._set_kind(span, "tool")
        tool_name = span.attributes.get("lk.function_tool.name")
        if tool_name:
            span._attributes["langsmith.metadata.tool_name"] = str(tool_name)
        args = span.attributes.get("lk.function_tool.arguments")
        if args is not None:
            span._attributes["gen_ai.prompt"] = (
                args if isinstance(args, str) else json.dumps(args)
            )
        output = span.attributes.get("lk.function_tool.output")
        if output is not None:
            span._attributes["gen_ai.completion"] = (
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
            thread_id: the conversation id, matching ``thread_id_provider``.
        """
        self._awaiting_recording.add(str(thread_id))

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
        self._awaiting_recording.discard(tid)
        trace_id = self._thread_to_trace.get(tid)
        if trace_id is not None:
            self._maybe_release(trace_id)

    # -- deferred root release ------------------------------------------------

    def _handle_root(self, span: ReadableSpan, trace_id: str) -> None:
        """Handle the trace root (job entrypoint), the conversation root.

        The root ends before the conversation completes (the agent greets first),
        so we always defer it and release it — complete, with audio — once the
        session has ended and any awaited recording has arrived.
        """
        self._set_kind(span, "chain")
        span._attributes["langsmith.root_span"] = True
        span._attributes["langsmith.metadata.ls_modality"] = "audio"

        thread = span.attributes.get("langsmith.metadata.thread_id")
        if thread is not None:
            self._thread_to_trace[str(thread)] = trace_id
            self._trace_to_thread[trace_id] = str(thread)

        self._deferred_root_spans[trace_id] = span
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
        span = self._deferred_root_spans.get(trace_id)
        if span is None or trace_id not in self._ended_sessions:
            return
        thread = self._trace_to_thread.get(trace_id)
        if thread is not None and thread in self._awaiting_recording:
            return  # still waiting for complete_recording()

        self._deferred_root_spans.pop(trace_id, None)
        self._render_conversation(span)
        self._attach_audio_recording(span)
        if thread is not None:
            self._attach_pending_audio(span, thread)
        self._export(span)
        self._cleanup_trace(trace_id)

    def _render_conversation(self, span: ReadableSpan) -> bool:
        """Render the accumulated conversation onto a root span.

        Input = the opening message; output = everything after it. Returns
        whether anything was rendered.
        """
        messages = self._conversation_by_trace.get(span.context.trace_id, [])
        if not messages:
            return False
        self._set_messages(span, prompt=messages[:1])
        if len(messages) > 1:
            self._set_messages(span, completion=messages[1:])
        return True

    def _cleanup_trace(self, trace_id: str) -> None:
        self._conversation_by_trace.pop(int(trace_id, 16), None)
        self._ended_sessions.discard(trace_id)
        thread = self._trace_to_thread.pop(trace_id, None)
        if thread is not None:
            self._thread_to_trace.pop(thread, None)
            self._awaiting_recording.discard(thread)
            self._pending_audio.pop(thread, None)

    def shutdown(self) -> None:
        """Flush any deferred root spans, then shut down the downstream."""
        self._flush_deferred_root_spans()
        super().shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush any deferred root spans, then force-flush the downstream."""
        self._flush_deferred_root_spans()
        return super().force_flush(timeout_millis)

    def _flush_deferred_root_spans(self) -> None:
        """Export any root spans still held.

        Covers a session that ended abnormally, or an awaited recording that
        never arrived before shutdown.
        """
        for trace_id, span in list(self._deferred_root_spans.items()):
            if not self._render_conversation(span):
                self._set_messages(
                    span,
                    prompt=[{"role": "system", "content": "Conversation not captured"}],
                    completion=[
                        {
                            "role": "assistant",
                            "content": "No conversation turns recorded.",
                        }
                    ],
                )
            self._attach_audio_recording(span)
            thread = self._trace_to_thread.get(trace_id)
            if thread is not None:
                self._attach_pending_audio(span, thread)
            self._export(span)
            del self._deferred_root_spans[trace_id]

    # -- audio attachment -----------------------------------------------------

    def _attach_audio_recording(self, span: ReadableSpan) -> None:
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
            span,
            name=audio_path.name,
            data=audio_bytes,
            mime_type=self._audio_mime_type,
        )

    def _attach_pending_audio(self, span: ReadableSpan, thread: str) -> None:
        """Embed a recording supplied via :meth:`complete_recording` (egress)."""
        pending = self._pending_audio.pop(thread, None)
        if not pending or not pending.get("data"):
            return
        self._attach_audio(
            span,
            name=pending["name"],
            data=pending["data"],
            mime_type=pending["mime_type"],
        )

    # -- realtime-model metrics ----------------------------------------------

    def _cache_realtime_metrics(self, span: ReadableSpan) -> None:
        """Stash a ``realtime_metrics`` span's data for its parent ``agent_turn``."""
        parent_id = span.parent.span_id if span.parent else None
        if parent_id is None:
            return
        cached = {
            k: v
            for k, v in span.attributes.items()
            if k.startswith("lk.") or k.startswith("gen_ai.usage")
        }
        # Lift token counts into gen_ai.usage.* for cost tracking.
        metrics = self._try_parse_json_object(
            span.attributes.get("lk.realtime_model_metrics")
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

    def _drain_realtime_metrics(self, span: ReadableSpan) -> None:
        """Copy cached realtime metrics onto this (agent_turn) span (if absent)."""
        cached = self._realtime_metrics_by_parent.pop(span.context.span_id, None)
        if not cached:
            return
        for k, v in cached.items():
            if k not in span._attributes:
                span._attributes[k] = v

    # -- blanket lk.* pass-through (runs just before export) ------------------

    def _pre_export(self, span: ReadableSpan) -> None:
        """Forward every ``lk.*`` attribute to ``langsmith.metadata.lk_<name>``.

        Scalars and sequences of scalars are forwarded directly; JSON-object
        blobs are flattened so each metric is its own field.
        """
        for key in list(span.attributes.keys()):
            if not key.startswith("lk."):
                continue
            v = span.attributes[key]
            if v is None or isinstance(v, dict):
                continue
            ms_key = f"langsmith.metadata.{key.replace('.', '_')}"
            parsed = self._try_parse_json_object(v)
            if parsed is not None:
                self._flatten_into_metadata(span, ms_key, parsed)
                continue
            if ms_key in span._attributes:  # don't clobber what a branch set
                continue
            span._attributes[ms_key] = v

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
        self, span: ReadableSpan, prefix: str, obj: dict, _depth: int = 0
    ) -> None:
        """Flatten a dict's scalar leaves to ``langsmith.metadata.<prefix>_<key>``."""
        if _depth > 4:
            return
        for k, v in obj.items():
            name = f"{prefix}_{k}"
            if isinstance(v, dict):
                self._flatten_into_metadata(span, name, v, _depth + 1)
            elif isinstance(v, (str, int, float, bool)):
                if name not in span._attributes:
                    span._attributes[name] = v
            elif (
                isinstance(v, (list, tuple))
                and v
                and all(isinstance(item, (str, int, float, bool)) for item in v)
            ):
                if name not in span._attributes:
                    span._attributes[name] = list(v)
