"""LangSmith tracing for Google ADK Live (``Runner.run_live``).

ADK emits ``gen_ai.*`` OTel spans for its non-live paths, but ``run_live`` — the
whole voice loop — isn't instrumented, so an OTel-only setup yields an empty
root. This integration builds the trace from the live event stream instead,
using ADK's official plugin hook: :class:`LangSmithGoogleADKLivePlugin` is a
``BasePlugin`` whose ``before_run_callback`` / ``on_event_callback`` /
``after_run_callback`` hooks open the conversation root span, span each
meaningful event, and finalize.

The plugin runs alongside the application's own ``run_live`` loop (which plays
audio and reacts to barge-ins) — it carries no application logic. Audio for the
stereo conversation WAV is fed by the app via :meth:`record_user_audio` /
:meth:`record_agent_audio` (recording at the speaker/mic boundary captures what
was actually *heard*, post-barge-in-truncation — more accurate than the audio
embedded in events).

The trace is a flat stream of the events as they arrive, each a point-in-time
span, with one exception: a tool call becomes a *single* ``tool`` span spanning
its ``function_call`` → ``function_response`` events (so the span duration is
the real tool latency, and the gap ADK spends running the tool is captured),
correlated by ``FunctionCall.id``. The events aren't grouped into synthetic
conversational ``turn`` spans: Gemini finalizes transcripts late — often after
the audio they describe has already played — so a turn's boundaries can't be
placed against the stereo-WAV timeline without reading as misaligned. Keeping
each span anchored to its own event's arrival keeps the trace legible against
the audio. (Transcript spans still trail the audio slightly for the same
finalization reason; that lag is inherent to the event stream.)

Trace shape — one conversation = one trace::

    realtime_session                       (root; transcript + stereo WAV)
    ├── input_transcription                (curated user_message — user speech)
    ├── get_weather                        (tool — args in / response out; real latency)
    ├── output_transcription               (agent speech + token usage)
    ├── turn_complete                      (marker)
    └── interrupted                        (marker — on barge-in)
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

from google.adk.plugins.base_plugin import BasePlugin

from langsmith import RunTree
from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal.voice.helpers import dump_event, observe_safely, scrub
from langsmith._internal.voice.session import EventSession, start_session

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langsmith import Client
    from langsmith.run_trees import WriteReplica

logger = logging.getLogger(__name__)

# ADK Live audio sample rate (used for the stereo conversation WAV).
DEFAULT_SAMPLE_RATE = 24_000


class _LiveEventView:
    """A readable view over one raw ADK ``run_live`` event.

    Every item the runner yields is the same ADK ``Event`` with all-optional
    fields; "what kind of event is this" is implicit in which fields are
    populated. This centralizes that field inspection.
    """

    def __init__(self, raw: Any) -> None:
        self.raw = raw

    @property
    def interrupted(self) -> bool:
        return bool(getattr(self.raw, "interrupted", False))

    @property
    def turn_complete(self) -> bool:
        return bool(getattr(self.raw, "turn_complete", False))

    @property
    def _parts(self) -> list[Any]:
        content = getattr(self.raw, "content", None)
        parts = getattr(content, "parts", None) if content else None
        return list(parts) if parts else []

    @property
    def audio_chunks(self) -> list[bytes]:
        return [
            p.inline_data.data
            for p in self._parts
            if getattr(p, "inline_data", None) and p.inline_data.data
        ]

    @property
    def function_calls(self) -> list[Any]:
        return [
            p.function_call
            for p in self._parts
            if getattr(p, "function_call", None) and p.function_call.name
        ]

    @property
    def function_responses(self) -> list[Any]:
        return [
            p.function_response
            for p in self._parts
            if getattr(p, "function_response", None) and p.function_response.name
        ]

    def _transcript(self, attr: str, *, final_only: bool) -> str | None:
        tx = getattr(self.raw, attr, None)
        if not (tx and getattr(tx, "text", None)):
            return None
        if final_only and not getattr(tx, "finished", False):
            return None
        return tx.text

    @property
    def user_transcript(self) -> str | None:
        return self._transcript("input_transcription", final_only=False)

    @property
    def agent_transcript(self) -> str | None:
        return self._transcript("output_transcription", final_only=False)

    @property
    def final_user_transcript(self) -> str | None:
        return self._transcript("input_transcription", final_only=True)

    @property
    def final_agent_transcript(self) -> str | None:
        return self._transcript("output_transcription", final_only=True)


def _usage_metadata(event: Any) -> dict[str, int] | None:
    """Map an ADK event's ``usage_metadata`` to LangSmith token usage, if any.

    ADK inherits genai's ``GenerateContentResponseUsageMetadata`` (prompt /
    candidates / total token counts). Live events may carry no usage at all, in
    which case the ``llm`` span is still recorded without token counts. Only
    the fields ADK actually reports are included.
    """
    um = getattr(event, "usage_metadata", None)
    if um is None:
        return None
    mapping = {
        "input_tokens": getattr(um, "prompt_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "total_tokens": getattr(um, "total_token_count", None),
    }
    usage = {k: v for k, v in mapping.items() if isinstance(v, int)}
    return usage or None


class _AdkLiveTracer:
    """Turns one conversation's ADK ``run_live`` event stream into spans.

    Holds the conversation's :class:`EventSession` plus the one piece of state
    the flat root layout still needs: the open ``tool`` spans awaiting their
    ``function_response`` (so a tool call is one span, not two events). One
    tracer per concurrent conversation — the plugin keys them by ADK session id.
    """

    def __init__(self, session: EventSession) -> None:
        self._trace = session
        # Open tool spans awaiting their function_response, keyed by
        # FunctionCall.id (falling back to the tool name when ADK omits an id).
        # A FIFO list per key disambiguates repeated/parallel identical calls.
        self._open_tools: dict[str, list[RunTree]] = {}

    @property
    def session(self) -> EventSession:
        return self._trace

    def observe(self, event: Any) -> None:
        """Observe one ``run_live`` event and emit its spans / rollups.

        Event categories are handled independently (not mutually exclusive):
        one event usually carries a single signal, but nothing assumes that.
        """
        view = _LiveEventView(event)
        t = self._trace.now()

        # A finalized user utterance: transcript rollup + title, and a curated
        # user_message span (raw event kept in metadata).
        fu = view.final_user_transcript
        if fu:
            self._trace.add_message("user", fu)
            self._trace.set_title(fu)
            with self._trace.event_span(
                event,
                t,
                name="input_transcription",
                inbound=True,
                inputs={"role": "user", "content": fu},
            ):
                pass

        # Tool calls / responses: one held-open ``tool`` span per call, from its
        # function_call to its matching function_response (the gap is the real
        # tool latency). See _start_tool / _end_tool.
        for call in view.function_calls:
            self._start_tool(call, event)
        for response in view.function_responses:
            self._end_tool(response, event, t)

        # A finalized agent utterance: transcript rollup plus a point-in-time
        # ``output_transcription`` span (raw event payload, token usage when ADK
        # reports it). Anchored at the event's arrival and left flat rather than
        # grouped into a synthetic turn: Gemini finalizes transcripts late (often
        # after the audio it describes), so a turn's boundaries can't be placed
        # against the audio timeline without reading as misaligned.
        fa = view.final_agent_transcript
        if fa:
            self._trace.add_message("assistant", fa)
            with self._trace.event_span(
                event,
                t,
                name="output_transcription",
                inbound=False,
                usage_metadata=_usage_metadata(event),
            ):
                pass

        # Barge-in and end-of-turn markers, each a point-in-time span.
        if view.interrupted:
            with self._trace.event_span(event, t, name="interrupted", inbound=False):
                pass
        if view.turn_complete:
            with self._trace.event_span(event, t, name="turn_complete", inbound=False):
                pass

    def _start_tool(self, call: Any, event: Any) -> None:
        """Open a held-open ``tool`` span for one ``function_call``.

        ``event`` (the whole enclosing ``Event``, not just the ``FunctionCall``)
        is stashed as ``raw_event`` so the tool span preserves the full wire
        payload — event id, author, timestamp, sibling parts — the flat layout
        used to keep, on top of the curated args.
        """
        name = getattr(call, "name", None) or "tool"
        run = self._trace.open_span(
            name=name,
            run_type="tool",
            inputs={"args": getattr(call, "args", None)},
            metadata={
                "function_call_id": getattr(call, "id", None),
                "raw_event": scrub(dump_event(event)),
            },
        )
        self._open_tools.setdefault(self._tool_key(call), []).append(run)

    def _end_tool(self, response: Any, event: Any, t: float) -> None:
        """Close the ``tool`` span matching one ``function_response``.

        Matched FIFO on ``FunctionCall.id`` (falling back to the tool name). If
        no open call matches — e.g. tracing began mid-call, or a merged parallel
        response — a point-in-time ``tool`` span is emitted instead so the call
        is still recorded. The full enclosing ``event`` is preserved as
        ``raw_event`` either way.
        """
        name = getattr(response, "name", None) or "tool"
        outputs = {"response": getattr(response, "response", None)}
        queue = self._open_tools.get(self._tool_key(response))
        if not queue and getattr(response, "id", None):
            queue = self._open_tools.get(name)  # id set but unmatched → try name
        if queue:
            run = queue.pop(0)
            self._prune_empty()
            self._trace.close_span(
                run, outputs=outputs, metadata={"raw_event": dump_event(event)}
            )
            return
        with self._trace.event_span(
            event,
            t,
            name=name,
            run_type="tool",
            inbound=False,
            inputs={},
            outputs=outputs,
        ):
            pass

    @staticmethod
    def _tool_key(call_or_response: Any) -> str:
        """FIFO key correlating a function_call to its function_response."""
        fid = getattr(call_or_response, "id", None)
        return str(fid) if fid else (getattr(call_or_response, "name", None) or "tool")

    def _prune_empty(self) -> None:
        """Drop tool-span queues emptied by their last matching response."""
        self._open_tools = {k: v for k, v in self._open_tools.items() if v}

    def flush_pending(self) -> None:
        """Close any tool span that never saw its response, with an error.

        Called at teardown: a tool that raised (ADK routes that through its own
        error handling, not a function_response event) or a session torn down
        mid-call would otherwise leave a span dangling open forever.
        """
        for queue in self._open_tools.values():
            for run in queue:
                run.error = "tool did not complete before the session ended"
                self._trace.close_span(run)
        self._open_tools.clear()


class LangSmithGoogleADKLivePlugin(BasePlugin):
    """An ADK ``BasePlugin`` that traces ``run_live`` conversations to LangSmith.

    Register it on the ``Runner`` (``Runner(..., plugins=[plugin])``). One run =
    one trace. Feed audio via :meth:`record_user_audio` / :meth:`record_agent_audio`
    to attach the stereo conversation WAV.

    A single plugin instance is shared across every ``run_live`` invocation on the
    Runner, so per-conversation state is keyed by ADK session id (see
    :meth:`_session_key`) and guarded by a lock — concurrent conversations each
    get their own isolated trace. Tracing is best-effort: every callback and audio
    recorder swallows and logs its own errors, so a tracing failure can never
    break the live loop or the app's audio path.
    """

    @warn_beta
    def __init__(
        self,
        *,
        name: str = "langsmith_live",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
        project_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        max_audio_seconds: Optional[float] = None,
        client: Optional[Client] = None,
        replicas: Optional[Sequence[WriteReplica]] = None,
    ) -> None:
        """Create the plugin.

        Args:
            name: plugin name (required by ``BasePlugin``).
            sample_rate: PCM sample rate of the audio (for the WAV).
            thread_id_provider: zero-arg callable returning the LangSmith thread
                id for the run; a random UUID per run if omitted.
            project_name: LangSmith project; defaults to standard config.
            tags / metadata: attached to the conversation root span.
            max_audio_seconds: per-channel cap on audio retained for the WAV, to
                bound memory. Since one shared plugin can trace many (and
                long-running) conversations, set this on a server to keep audio
                buffers from growing unbounded; ``None`` (default) keeps all audio.
            client: LangSmith ``Client`` for tracing writes; ``None`` (default)
                uses the SDK's standard env-based resolution (``LANGSMITH_*``).
            replicas: tracing replicas to mirror the conversation trace to
                additional destinations; ``None`` (default) disables replication.
        """
        super().__init__(name=name)
        self._sample_rate = sample_rate
        self._thread_id_provider = thread_id_provider
        self._project_name = project_name
        self._tags = tags
        self._metadata = metadata
        self._max_audio_seconds = max_audio_seconds
        self._client = client
        self._replicas = replicas
        # One tracer per concurrent conversation, keyed by ADK session id. The
        # plugin instance is shared across all run_live invocations, so a single
        # attribute would let concurrent conversations clobber each other. The
        # lock guards this dict (not the per-session audio buffers) so the audio
        # thread and the event loop can touch it without racing.
        self._sessions: dict[str, _AdkLiveTracer] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _session_key(invocation_context: Any) -> str:
        """Stable per-conversation key from an ADK ``InvocationContext``.

        Prefers the ADK session id (the app knows it and can pass it to the
        audio recorders), falling back to the invocation id, then object identity.
        """
        session = getattr(invocation_context, "session", None)
        sid = getattr(session, "id", None)
        if sid:
            return str(sid)
        inv = getattr(invocation_context, "invocation_id", None)
        return str(inv) if inv else str(id(invocation_context))

    def _resolve_tracer(self, session_id: Optional[str]) -> Optional[_AdkLiveTracer]:
        """Pick the tracer a recorded audio chunk belongs to.

        With an explicit ``session_id`` the lookup is exact. Without one, audio
        is routed to the sole active session when exactly one exists (the common
        single-conversation case); when zero or several are active it is dropped,
        since the chunk cannot be attributed unambiguously.
        """
        with self._lock:
            if session_id is not None:
                return self._sessions.get(str(session_id))
            if len(self._sessions) == 1:
                return next(iter(self._sessions.values()))
            return None

    # -- app-fed audio --------------------------------------------------------

    def record_user_audio(
        self, pcm: bytes, *, session_id: Optional[str] = None
    ) -> None:
        """Record a chunk of user (mic) PCM16 for the stereo conversation WAV.

        Pass ``session_id`` (the ADK session id) to disambiguate when multiple
        conversations are traced concurrently; omit it for the single-session case.
        """
        try:
            tracer = self._resolve_tracer(session_id)
            if tracer is not None:
                tracer.session.record_user(tracer.session.now(), pcm)
        except Exception:
            logger.debug("LangSmith: failed to record user audio", exc_info=True)

    def record_agent_audio(
        self, pcm: bytes, *, session_id: Optional[str] = None
    ) -> None:
        """Record a chunk of agent (played) PCM16 for the stereo conversation WAV.

        Pass ``session_id`` (the ADK session id) to disambiguate when multiple
        conversations are traced concurrently; omit it for the single-session case.
        """
        try:
            tracer = self._resolve_tracer(session_id)
            if tracer is not None:
                tracer.session.record_agent(tracer.session.now(), pcm)
        except Exception:
            logger.debug("LangSmith: failed to record agent audio", exc_info=True)

    # -- ADK plugin callbacks -------------------------------------------------

    async def before_run_callback(self, *, invocation_context: Any) -> None:
        try:
            thread_id = (
                self._thread_id_provider() if self._thread_id_provider else None
            ) or str(uuid.uuid4())
            session = start_session(
                thread_id=thread_id,
                sample_rate=self._sample_rate,
                project_name=self._project_name,
                tags=self._tags,
                metadata=self._metadata,
                max_audio_seconds=self._max_audio_seconds,
                client=self._client,
                replicas=self._replicas,
            )
            key = self._session_key(invocation_context)
            with self._lock:
                self._sessions[key] = _AdkLiveTracer(session)
        except Exception:
            logger.debug("LangSmith: failed to start live session", exc_info=True)

    async def on_event_callback(self, *, invocation_context: Any, event: Any) -> None:
        key = self._session_key(invocation_context)
        with self._lock:
            tracer = self._sessions.get(key)
        if tracer is None:
            return
        # observe_safely keeps a tracing error from escaping into the live loop.
        observe_safely(tracer.observe, event)

    async def after_run_callback(self, *, invocation_context: Any) -> None:
        """Finalize the conversation trace (roll up the transcript, attach WAV).

        ADK fires this once per run — with that run's ``invocation_context`` —
        from a ``finally`` in the runner, so on a graceful end (the input queue
        closing, as on a hang-up) the matching session is finalized automatically.

        On a *cancelled* run (e.g. a console Ctrl-C that tears the loop down),
        ADK may not fire this, and ``run_live`` may not drain promptly. For that
        case finalize the conversation yourself with :meth:`finalize`, passing the
        ADK session id — it is keyed and idempotent with this callback.

        Idempotent: the session is popped under the lock, so a second call finds
        nothing to finalize.
        """
        try:
            self._finalize_key(self._session_key(invocation_context))
        except Exception:
            logger.debug("LangSmith: failed to finalize live session", exc_info=True)

    def finalize(self, *, session_id: str) -> None:
        """Finalize one conversation's trace early, keyed by ADK session id.

        For app-driven teardown when ADK's :meth:`after_run_callback` can't be
        relied on — most often a console app that cancels ``run_live`` on Ctrl-C,
        where ADK does not (reliably) fire its callback and the audio attachment
        (built only at finalize) would otherwise be lost. Pass the same
        ``session_id`` used for ``run_live``.

        Idempotent and keyed: an unknown id, or a repeat call after ADK's own
        callback already finalized, is a no-op.
        """
        try:
            self._finalize_key(str(session_id))
        except Exception:
            logger.debug("LangSmith: failed to finalize live session", exc_info=True)

    def _finalize_key(self, key: str) -> None:
        """Pop the tracer for ``key`` under the lock and finalize it (if any)."""
        with self._lock:
            tracer = self._sessions.pop(key, None)
        if tracer is not None:
            # Close any tool span still awaiting its response before the root.
            tracer.flush_pending()
            tracer.session.finalize()
