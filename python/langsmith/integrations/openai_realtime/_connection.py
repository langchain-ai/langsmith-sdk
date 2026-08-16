"""LangSmith tracing for the OpenAI Realtime API (raw WebSocket).

OpenAI Realtime has no native telemetry — it's a raw WebSocket event stream of
``input_audio_buffer.*`` / ``response.*`` events. :func:`wrap_realtime` wraps the
``AsyncRealtimeConnection`` so the trace is built directly from that stream while
the caller's ``async for event in connection`` loop is left untouched: each
received event is observed, spanned where warranted, and grouped into turns; the
running transcript and a stereo conversation WAV land on the root span.

Tool nesting is preserved without wrapping the caller's loop body: an event's
span is opened when the event is received and kept as the active LangSmith
context until the *next* event arrives — so any ``@traceable`` work the caller
does while handling the event (tool execution) nests under it.

Trace shape — one conversation = one trace::

    realtime_session                                   (root; transcript + WAV)
    ├── session.created / session.updated              (setup)
    ├── turn                                           (latency_ms, was_interrupted)
    │   ├── conversation.item.input_audio_transcription.completed   (user message)
    │   └── response.done                              (chain wrapper)
    │       ├── model                                  (llm — message + tokens)
    │       └── <your @traceable tools>                (nested under response.done)
    └── turn …
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

from langsmith._internal._package_version import get_package_version
from langsmith._internal._usage import _create_usage_metadata
from langsmith._internal.voice.helpers import observe_safely
from langsmith._internal.voice.session import (
    DEFAULT_MAX_AUDIO_SECONDS,
    EventSession,
    start_session,
)
from langsmith.run_helpers import tracing_context

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langsmith import Client, RunTree
    from langsmith.run_trees import WriteReplica

logger = logging.getLogger(__name__)

# Default PCM sample rate for OpenAI Realtime audio (used for the stereo WAV).
DEFAULT_SAMPLE_RATE = 24_000

# Structural bookkeeping events that only duplicate state already captured by
# ``response.done`` and the transcript events, so spanning them floods the trace.
NOISE_EVENTS = frozenset(
    {
        "input_audio_buffer.committed",
        "conversation.item.added",
        "conversation.item.done",
        "response.created",
        "response.output_item.added",
        "response.output_item.done",
        "response.content_part.added",
        "response.content_part.done",
        "response.output_audio.done",
        # Redundant with the model span's tool_calls + the tool span's args.
        "response.function_call_arguments.done",
    }
)


def is_inbound(event_type: str) -> bool:
    """Direction of an event relative to the model.

    Inbound = something the user sent toward the model (their speech buffer,
    their transcription) → goes in span ``inputs``. Everything else is the
    model/server talking back → span ``outputs``.
    """
    return (
        event_type.startswith("input_audio_buffer")
        or "input_audio_transcription" in event_type
    )


def response_assistant_output(response: Any) -> dict[str, Any]:
    """Curated assistant message from a ``response.done`` payload.

    The readable, AIMessage-shaped view of what the model returned this
    response: the spoken text plus any tool calls it requested. Tool calls use
    the OpenAI ChatCompletion shape (``type: "function"`` with a nested
    ``function`` holding the name and the raw JSON ``arguments`` string) — that's
    the format the LangSmith UI recognizes and renders inline on the model span;
    a flatter ``{name, args, id}`` shape would instead spill into "Additional
    Fields".
    """
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) == "function_call":
            tool_calls.append(
                {
                    "id": getattr(item, "call_id", None),
                    "type": "function",
                    "index": len(tool_calls),
                    "function": {
                        "name": getattr(item, "name", None),
                        # The wire ``arguments`` JSON string is passed through
                        # verbatim: the UI expects a string here, not an object.
                        "arguments": getattr(item, "arguments", None) or "{}",
                    },
                }
            )
            continue
        for part in getattr(item, "content", None) or []:
            text = getattr(part, "transcript", None) or getattr(part, "text", None)
            if text:
                texts.append(text)
    out: dict[str, Any] = {"role": "assistant", "content": " ".join(texts).strip()}
    if tool_calls:
        out["tool_calls"] = tool_calls
    return out


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    """Normalize a Realtime ``usage`` object into the dict the shared mapper reads.

    Realtime spells its per-modality breakdowns ``input_token_details`` /
    ``output_token_details`` (singular "token"), whereas
    :func:`_create_usage_metadata` looks for the Chat-Completions
    ``*_tokens_details`` spelling — so we alias them here to let it pick up audio
    and cached-token detail (which dominate voice cost). Falls back to the
    top-level token counts if the object can't be dumped, omitting the detail
    blocks rather than risk passing non-dict values to the mapper.
    """
    if isinstance(usage, dict):
        base = dict(usage)
    else:
        model_dump = getattr(usage, "model_dump", None)
        try:
            base = dict(model_dump()) if callable(model_dump) else {}
        except Exception:
            base = {}
        if not base:
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                val = getattr(usage, key, None)
                if val is not None:
                    base[key] = val
    for realtime_key, mapper_key in (
        ("input_token_details", "input_tokens_details"),
        ("output_token_details", "output_tokens_details"),
    ):
        block = base.get(realtime_key)
        if isinstance(block, dict) and mapper_key not in base:
            base[mapper_key] = block
    return base


def usage_metadata_from_usage(usage: Any) -> dict[str, Any] | None:
    """Map a Realtime ``usage`` (object or dict) onto LangSmith ``usage_metadata``.

    Delegates to the shared OpenAI usage mapper so the Realtime integration and
    the Chat/Agents wrappers agree on the canonical shape (and so audio/cached
    token detail is captured, not dropped). Returns ``None`` when there is no
    usage or it carries no token counts (e.g. a cancelled turn).
    """
    if usage is None:
        return None
    usage_dict = _usage_to_dict(usage)
    if not any(
        usage_dict.get(key) is not None
        for key in ("input_tokens", "output_tokens", "total_tokens")
    ):
        return None
    return dict(_create_usage_metadata(usage_dict))


def response_usage_metadata(response: Any) -> dict[str, Any] | None:
    """Map a ``response.done`` payload's token ``usage`` onto ``usage_metadata``."""
    return usage_metadata_from_usage(getattr(response, "usage", None))


class _RealtimeTracer:
    """Turns the Realtime event stream into a LangSmith trace, one event at a time.

    Decides — privately — whether to open a span, open/close a turn, append to
    the transcript rollup, set the trace title, time first-audio latency, flag a
    barge-in, and record the ``llm`` span. All trace writes go through the
    injected :class:`EventSession`.

    An event's span is held open (as the active LangSmith parent context) from
    the moment the event is received until the next event arrives, so the
    caller's tool calls nest under it.
    """

    def __init__(
        self,
        session: EventSession,
        *,
        is_agent_speaking: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._session = session
        # The only way to know the agent was still audible when the user spoke (a
        # barge-in) is whether playback is still queued; the wire stream has no
        # "playout finished" event. Optional — supplied by the app.
        self._is_agent_speaking = is_agent_speaking
        # Per-turn latency: end-of-user-speech → first agent audio. Armed at
        # speech_stopped, recorded on the first audio chunk. None = not armed.
        self._await_audio_since: float | None = None
        # The currently open event span, kept active until the next event:
        # (event_span_cm, tracing_context_cm). None = nothing open.
        self._open: tuple[Any, Any] | None = None
        self._model: str | None = None

    def observe(self, event: Any) -> None:
        """Observe one received event; span it where warranted.

        Closes the previous event's span first (the caller has finished handling
        it), then applies turn/transcript/latency side-state and, for meaningful
        events, opens a new span kept active until the next call.
        """
        self._close_open()
        received_at = self._session.now()
        etype = getattr(event, "type", None)
        if etype is None:
            return  # not a recognizable Realtime event; nothing to span

        # Capture the session's model (for the llm span's ls_model_name); the
        # response.done payload has no model field, but the session events do.
        if etype in ("session.created", "session.updated"):
            model = getattr(getattr(event, "session", None), "model", None)
            if model:
                self._model = str(model)

        # No-span events: observed for side-state only.
        if etype == "response.output_audio.delta":
            self._record_first_audio(received_at)
            return
        if etype.endswith(".delta") or etype in NOISE_EVENTS:
            return
        if etype == "response.output_audio_transcript.done":
            # Already the model span's content; fold into the rollup, don't span.
            self._session.add_message(
                "assistant", getattr(event, "transcript", "") or ""
            )
            return

        self._before_span(event, received_at)

        cm_span = self._session.event_span(
            event, received_at, name=etype, **self._span_kwargs(event)
        )
        run = cm_span.__enter__()
        if etype == "conversation.item.input_audio_transcription.failed":
            run.error = f"transcription_failed: {getattr(event, 'error', None)}"
        elif etype == "response.done":
            response = getattr(event, "response", None)
            if response is not None:
                self._record_response_llm(run, response)
        cm_ctx = tracing_context(parent=run)
        cm_ctx.__enter__()
        self._open = (cm_span, cm_ctx)

    def finalize_open(self) -> None:
        """Close any still-open event span (called at teardown)."""
        self._close_open()

    def _close_open(self) -> None:
        if self._open is None:
            return
        cm_span, cm_ctx = self._open
        self._open = None
        cm_ctx.__exit__(None, None, None)
        cm_span.__exit__(None, None, None)

    def _before_span(self, event: Any, received_at: float) -> None:
        """Turn/transcript/title side-state applied as a span is about to open."""
        etype = event.type
        if etype == "input_audio_buffer.speech_started":
            # A user starting to speak opens a new turn (also the barge-in
            # signal). If the agent was still audible, the turn being closed was
            # talked over — flag it before start_turn() closes it.
            if self._is_agent_speaking is not None and self._is_agent_speaking():
                self._session.add_turn_metadata(was_interrupted=True)
            self._session.start_turn()
            self._await_audio_since = None
        elif etype == "input_audio_buffer.speech_stopped":
            self._await_audio_since = received_at
        elif etype == "conversation.item.input_audio_transcription.completed":
            text = (getattr(event, "transcript", "") or "").strip()
            if text:
                self._session.add_message("user", text)
                self._session.set_title(text)
            else:
                self._await_audio_since = None
        elif etype == "conversation.item.input_audio_transcription.failed":
            self._await_audio_since = None

    def _span_kwargs(self, event: Any) -> dict[str, Any]:
        """Curated, conversation-shaped I/O for the readable events."""
        etype = event.type
        kwargs: dict[str, Any] = {"inbound": is_inbound(etype)}
        if etype == "conversation.item.input_audio_transcription.completed":
            text = (getattr(event, "transcript", "") or "").strip()
            if text:
                kwargs["inputs"] = {"role": "user", "content": text}
        elif etype == "response.done":
            # Keep this a chain wrapper; the model payload goes on the child llm
            # span so local tool latency isn't attributed to the model.
            kwargs["outputs"] = {}
        return kwargs

    def _record_first_audio(self, received_at: float) -> None:
        if self._await_audio_since is not None:
            self._session.add_turn_metadata(
                latency_to_first_audio_ms=round(
                    (received_at - self._await_audio_since) * 1000
                )
            )
            self._await_audio_since = None

    def _record_response_llm(self, run: RunTree, response: Any) -> None:
        metadata: dict[str, Any] = {
            "status": getattr(response, "status", None),
            "ls_provider": "openai",
            "ls_model_name": self._model,
        }
        self._session.record_llm(
            run,
            outputs=response_assistant_output(response),
            usage_metadata=response_usage_metadata(response),
            metadata=metadata,
        )


class _TracedRealtimeConnection:
    """Transparent proxy over an ``AsyncRealtimeConnection`` that traces events.

    Delegates every attribute to the wrapped connection, so the caller uses it
    exactly like the original (``connection.session.update(...)``,
    ``connection.response.create()``, ``async for event in connection``). Each
    received event is passed to the tracer. Also exposes
    :meth:`record_user_audio` / :meth:`record_agent_audio` so the app can
    (optionally) feed PCM for the stereo conversation WAV.
    """

    def __init__(
        self, connection: Any, tracer: _RealtimeTracer, session: EventSession
    ) -> None:
        # Plain assignment is safe: this proxy only overrides ``__getattr__``
        # (read miss) — not ``__setattr__`` — so writes never delegate.
        self._connection = connection
        self._tracer = tracer
        self._session = session
        self._aiter = None

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_connection"), name)

    def __aiter__(self) -> _TracedRealtimeConnection:
        self._aiter = self._connection.__aiter__()
        return self

    async def __anext__(self) -> Any:
        aiter = self._aiter
        if aiter is None:
            aiter = self._connection.__aiter__()
            self._aiter = aiter
        event = await aiter.__anext__()
        observe_safely(self._tracer.observe, event)
        return event

    async def recv(self) -> Any:
        event = await self._connection.recv()
        observe_safely(self._tracer.observe, event)
        return event

    def record_user_audio(self, pcm: bytes) -> None:
        """Record a chunk of user (mic) PCM16 for the stereo conversation WAV."""
        self._session.record_user(self._session.now(), pcm)

    def record_agent_audio(self, pcm: bytes) -> None:
        """Record a chunk of agent (played) PCM16 for the stereo conversation WAV."""
        self._session.record_agent(self._session.now(), pcm)


class _RealtimeTracingSession:
    """Async context manager returned by :func:`wrap_realtime`.

    On enter: starts the conversation root span and session-level LangSmith
    context, returning a traced connection proxy. On exit: closes any open span,
    records an error on the root if the body raised, and finalizes the root
    (rolling up the transcript + attaching the stereo WAV).
    """

    def __init__(
        self,
        connection: Any,
        *,
        thread_id: Optional[str],
        sample_rate: int,
        project_name: Optional[str],
        tags: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
        is_agent_speaking: Optional[Callable[[], bool]],
        max_audio_seconds: Optional[float],
        client: Optional[Client],
        replicas: Optional[Sequence[WriteReplica]],
    ) -> None:
        self._connection = connection
        self._thread_id = thread_id or str(uuid.uuid4())
        self._sample_rate = sample_rate
        self._project_name = project_name
        self._tags = tags
        self._metadata = metadata
        self._is_agent_speaking = is_agent_speaking
        self._max_audio_seconds = max_audio_seconds
        self._client = client
        self._replicas = replicas
        self._session: EventSession | None = None
        self._tracer: _RealtimeTracer | None = None
        self._ctx: Any = None

    async def __aenter__(self) -> _TracedRealtimeConnection:
        self._session = start_session(
            thread_id=self._thread_id,
            sample_rate=self._sample_rate,
            project_name=self._project_name,
            tags=self._tags,
            metadata=self._metadata,
            max_audio_seconds=self._max_audio_seconds,
            client=self._client,
            replicas=self._replicas,
            integration="openai-realtime",
            integration_version=get_package_version("openai"),
        )
        self._ctx = tracing_context(
            metadata={"thread_id": self._thread_id},
            tags=self._tags,
            project_name=self._project_name,
            replicas=self._replicas,
        )
        self._ctx.__enter__()
        self._tracer = _RealtimeTracer(
            self._session, is_agent_speaking=self._is_agent_speaking
        )
        return _TracedRealtimeConnection(self._connection, self._tracer, self._session)

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # Teardown is best-effort: closing the trace must neither mask the
        # caller's own exception nor raise a new one. The tracing context is
        # always restored (``finally``) so it can't leak past the session.
        try:
            if self._tracer is not None:
                self._tracer.finalize_open()
            if self._session is not None:
                if exc is not None:
                    self._session.run.error = f"{exc_type.__name__}: {exc}"
                self._session.finalize()
        except Exception:
            logger.warning("voice tracing: failed to finalize session", exc_info=True)
        finally:
            if self._ctx is not None:
                self._ctx.__exit__(None, None, None)
        return False


def wrap_realtime(
    connection: Any,
    *,
    thread_id: Optional[str] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    is_agent_speaking: Optional[Callable[[], bool]] = None,
    max_audio_seconds: Optional[float] = DEFAULT_MAX_AUDIO_SECONDS,
    client: Optional[Client] = None,
    replicas: Optional[Sequence[WriteReplica]] = None,
) -> _RealtimeTracingSession:
    r"""Trace an OpenAI Realtime connection into LangSmith.

    Returns an async context manager that yields a transparent proxy of
    ``connection``; iterate and call it exactly as you would the original::

        async with client.realtime.connect(model=...) as raw, \\
                   wrap_realtime(raw, thread_id=tid) as connection:
            async for event in connection:
                ...

    To capture the stereo conversation WAV, feed PCM via the proxy's
    ``record_user_audio`` / ``record_agent_audio`` and (optionally) supply
    ``is_agent_speaking`` so barge-ins are flagged.

    Args:
        connection: the ``AsyncRealtimeConnection`` from ``client.realtime.connect``.
        thread_id: LangSmith thread id; a random UUID if omitted.
        sample_rate: PCM sample rate of the audio (for the WAV).
        project_name: LangSmith project; defaults to standard ``LANGSMITH_*`` config.
        tags / metadata: attached to the conversation root span.
        is_agent_speaking: zero-arg callable returning whether the agent is still
            audible, used to flag a barge-in; ``None`` disables that flag.
        max_audio_seconds: per-channel cap on audio retained for the WAV, to
            bound memory on long sessions; pass ``None`` to keep all audio.
        client: LangSmith ``Client`` for tracing writes; ``None`` (default) uses
            the SDK's standard env-based resolution (``LANGSMITH_*``).
        replicas: tracing replicas to mirror the conversation trace to additional
            destinations; ``None`` (default) disables replication.
    """
    return _RealtimeTracingSession(
        connection,
        thread_id=thread_id,
        sample_rate=sample_rate,
        project_name=project_name,
        tags=tags,
        metadata=metadata,
        is_agent_speaking=is_agent_speaking,
        max_audio_seconds=max_audio_seconds,
        client=client,
        replicas=replicas,
    )
