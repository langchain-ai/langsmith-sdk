"""LangSmith tracing for the OpenAI Agents SDK realtime backend.

The Agents SDK's realtime sessions emit no local SDK trace spans (realtime
tracing is server-side only), so the existing batch ``OpenAIAgentsTracingProcessor``
captures nothing here. This is a separate, complementary integration:
:func:`wrap_realtime_session` wraps the ``RealtimeSession`` so the trace is built
from its **semantic event stream**, while the caller's ``async for event in
session`` loop is left untouched.

The conversation is reconstructed from the full ``history`` snapshot the session
delivers on every ``history_updated`` — not from the streamed events, which
mis-deliver user messages and emit the assistant transcript as growing partials.
Snapshots are folded into an item map keyed by stable ``item_id`` (latest text
per id wins → partials collapse); each finalized message emits one span (a
curated ``user_message`` or an assistant ``model`` ``llm`` span), grouped into
turns. Each SDK-run tool becomes a single ``tool`` span spanning its
``tool_start``→``tool_end`` pair (so the span duration is the real tool latency);
``audio_interrupted`` flags the turn. (Token usage isn't available — the SDK has
no per-response usage events yet.)

Trace shape — one conversation = one trace::

    realtime_session                                   (root; transcript + WAV)
    ├── turn                                           (latency_ms, was_interrupted)
    │   ├── user_message                               (curated user msg, from history)
    │   ├── lookup_weather                             (tool — args in / output out)
    │   └── model             (assistant message)      (llm — from history)
    └── turn …
"""

from __future__ import annotations

import dataclasses
import logging
import sys
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice.helpers import observe_safely
from langsmith._internal.voice.session import EventSession, start_session
from langsmith.run_helpers import tracing_context

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langsmith import Client, RunTree
    from langsmith.run_trees import WriteReplica

logger = logging.getLogger(__name__)

# Default PCM sample rate for OpenAI Realtime audio (used for the stereo WAV).
DEFAULT_SAMPLE_RATE = 24_000

_MAX_DEPTH = 4  # how deep we recurse into nested SDK objects before bailing
_MAX_ITEMS = 50  # cap on collection width so one event never balloons a span
_MAX_REPR = 200  # truncate the repr() fallback for exotic objects


# ---------------------------------------------------------------------------
# Payload shaping: turn the SDK's semantic event (a dataclass holding live SDK
# objects) into a compact, JSON-able span payload.
# ---------------------------------------------------------------------------


def _stringify(value: Any) -> Any:
    """Keep JSON-able values as-is; repr anything exotic so a span never breaks."""
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    return repr(value)


def _shallow(value: Any) -> Any:
    """Last-resort view of a value we won't (or can't) recurse into."""
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    text = repr(value)
    return text if len(text) <= _MAX_REPR else text[:_MAX_REPR] + "…"


def _public_fields(value: Any) -> dict[str, Any] | None:
    """Public, non-callable attributes of a dataclass/object, or None."""
    fields: dict[str, Any] | None
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {
            f.name: getattr(value, f.name, None) for f in dataclasses.fields(value)
        }
    else:
        fields = getattr(value, "__dict__", None)
    if not fields:
        return None
    return {
        k: v for k, v in fields.items() if not k.startswith("_") and not callable(v)
    }


def _clean(value: Any, depth: int = 0, seen: frozenset[int] = frozenset()) -> Any:
    """Recursively coerce any value into a compact, JSON-able span payload.

    Keeps readable data and strips what would break or bloat a span: raw bytes,
    callables, private attributes, and anything past the depth/width caps. Cycles
    are broken via ``seen``.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(value))} bytes>"

    if depth >= _MAX_DEPTH:
        return _shallow(value)
    if id(value) in seen:
        return "<circular>"
    seen = seen | {id(value)}

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (key, val) in enumerate(value.items()):
            if i >= _MAX_ITEMS:
                out["…"] = f"+{len(value) - _MAX_ITEMS} more"
                break
            if isinstance(key, str) and key.startswith("_"):
                continue
            out[str(key)] = _clean(val, depth + 1, seen)
        return out

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        cleaned = [_clean(v, depth + 1, seen) for v in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            cleaned.append(f"… +{len(items) - _MAX_ITEMS} more")
        return cleaned

    fields = _public_fields(value)
    if fields:
        return {k: _clean(v, depth + 1, seen) for k, v in fields.items()}
    return _shallow(value)


def _tool_name(tool: Any) -> str | None:
    return getattr(tool, "name", None) or (repr(tool) if tool is not None else None)


def _item_text(item: Any) -> tuple[str | None, str | None]:
    """Best-effort ``(role, text)`` for a realtime history item."""
    if item is None:
        return None, None
    role = getattr(item, "role", None)
    content = getattr(item, "content", None) or []
    parts = []
    for part in content:
        text = getattr(part, "transcript", None) or getattr(part, "text", None)
        if text:
            parts.append(text)
    return role, (" ".join(parts) or None)


def raw_input_transcript(event: Any) -> tuple[str | None, str] | None:
    """Extract the user transcript from a ``raw_model_event``.

    Reads a ``raw_model_event`` wrapping an input-audio transcription completion
    (the wire-level source ``history`` can omit on a barge-in). Returns
    ``(item_id, transcript)`` or None.
    """
    data = getattr(event, "data", None)
    if getattr(data, "type", None) != "input_audio_transcription_completed":
        return None
    transcript = (getattr(data, "transcript", None) or "").strip()
    if not transcript:
        return None
    return getattr(data, "item_id", None), transcript


def history_item(event: Any) -> tuple[str | None, str | None, str | None]:
    """``(item_id, role, text)`` for a ``history_added`` event's single item."""
    item = getattr(event, "item", None)
    role, text = _item_text(item)
    return getattr(item, "item_id", None), role, text


def history_messages(event: Any) -> list[tuple[str | None, str | None, str | None]]:
    """``(item_id, role, text)`` for every item in a ``history_updated`` snapshot."""
    out: list[tuple[str | None, str | None, str | None]] = []
    for item in getattr(event, "history", None) or []:
        role, text = _item_text(item)
        out.append((getattr(item, "item_id", None), role, text))
    return out


def describe_event(event: Any) -> tuple[str, dict[str, Any], bool]:
    """Map a session event to ``(name, span_payload, inbound)``."""
    etype = getattr(event, "type", None) or repr(event)
    dumped = _clean(event)
    payload: dict[str, Any] = dumped if isinstance(dumped, dict) else {"value": dumped}
    payload["type"] = etype
    inbound = False

    if etype in ("agent_start", "agent_end"):
        payload["agent"] = getattr(getattr(event, "agent", None), "name", None)
    elif etype == "tool_start":
        payload["tool"] = _tool_name(getattr(event, "tool", None))
        payload["arguments"] = _stringify(getattr(event, "arguments", None))
        inbound = True  # the model is asking us to run something → its input
    elif etype == "tool_end":
        payload["tool"] = _tool_name(getattr(event, "tool", None))
        payload["arguments"] = _stringify(getattr(event, "arguments", None))
        payload["output"] = _stringify(getattr(event, "output", None))
    elif etype == "audio_interrupted":
        payload["item_id"] = getattr(event, "item_id", None)
    elif etype == "history_added":
        role, text = _item_text(getattr(event, "item", None))
        payload["role"], payload["text"] = role, text
        inbound = role == "user"
    elif etype == "history_updated":
        history = getattr(event, "history", None) or []
        role, text = _item_text(history[-1]) if history else (None, None)
        payload["last_role"], payload["last_text"] = role, text
        payload["length"] = len(history)
        inbound = role == "user"
    elif etype == "handoff":
        payload["from_agent"] = getattr(
            getattr(event, "from_agent", None), "name", None
        )
        payload["to_agent"] = getattr(getattr(event, "to_agent", None), "name", None)
    elif etype == "guardrail_tripped":
        payload["message"] = _stringify(getattr(event, "message", None))
    elif etype == "error":
        payload["error"] = _stringify(getattr(event, "error", None))

    return etype, payload, inbound


def _resolve_model(session: Any) -> Optional[str]:
    """Best-effort model name for a ``RealtimeSession`` (attribution only).

    The Agents SDK emits no per-response usage, so this never drives cost; it
    just tags the assistant ``llm`` span with ``ls_model_name``. Returns ``None``
    when the model can't be read from the session.
    """
    model = getattr(session, "model", None)
    if isinstance(model, str):
        return model or None
    for attr in ("model_name", "model"):
        name = getattr(model, attr, None)
        if isinstance(name, str) and name:
            return name
    return None


class _AgentsRealtimeTracer:
    """Reconstructs the conversation from history snapshots and emits its spans.

    Folds each ``history`` snapshot into a map keyed by stable ``item_id``
    (latest non-empty text wins, so partials collapse), emits one span per
    finalized message (a ``user_message`` or an assistant ``model`` ``llm`` span)
    grouped into per-user-turn ``turn`` spans, and spans ``tool_end`` /
    ``audio_interrupted`` from the live stream. Optionally notifies an
    ``on_message`` callback as finalized transcript lines arrive.
    """

    def __init__(
        self,
        session: EventSession,
        *,
        on_message: Optional[Callable[[str, str], None]] = None,
        model: Optional[str] = None,
    ) -> None:
        self._trace = session
        self._on_message = on_message
        self._model = model
        # item_id → {"role", "text"}, in arrival order (dict preserves insertion).
        self._items: dict[str, dict[str, Any]] = {}
        self._emitted: set[str] = set()  # item_ids already turned into spans
        self._notified: set[tuple[str, str]] = set()  # (role, text) already sent out
        # Per-turn latency: when the current user turn opened; None = not armed.
        self._latency_since: float | None = None
        # Open tool spans, keyed by (tool_name, arguments). The SDK's
        # tool_start/tool_end events carry no call_id, so start→end is matched on
        # that pair; a FIFO list per key disambiguates the (rare) concurrent or
        # repeated identical calls in async-tool mode.
        self._open_tools: dict[tuple[str | None, str | None], list[RunTree]] = {}

    def observe(self, event: Any) -> None:
        """Observe one session event: fold history, emit spans, time latency."""
        received_at = self._trace.now()
        etype = getattr(event, "type", None)
        if etype is None:
            return  # not a recognizable session event; nothing to trace

        if etype == "audio":
            self.record_first_audio(received_at)
            return
        if etype == "raw_model_event":
            rec = raw_input_transcript(event)
            if rec:
                item_id, transcript = rec
                self._observe_items([(item_id, "user", transcript)], received_at)
                self._flush(hold_last=True)
            return
        if etype == "history_added":
            self._observe_items([history_item(event)], received_at)
            self._flush(hold_last=True)
            return
        if etype == "history_updated":
            self._observe_items(history_messages(event), received_at)
            self._flush(hold_last=True)
            return
        if etype in ("agent_start", "agent_end"):
            return  # bookkeeping markers, no I/O
        # A tool call is one span spanning tool_start → tool_end: the gap between
        # the two events is the real tool latency (the SDK runs the tool between
        # them), so they're held open rather than spanned point-in-time.
        if etype == "tool_start":
            self._start_tool(event)
            return
        if etype == "tool_end":
            self._end_tool(event, received_at)
            return

        # Remaining live events get a point-in-time span; a barge-in flags the
        # open turn.
        name, payload, inbound = describe_event(event)
        if etype == "audio_interrupted":
            self._trace.add_turn_metadata(was_interrupted=True)

        # No nested work happens while handling these events, so open+close now.
        with self._trace.event_span(payload, received_at, name=name, inbound=inbound):
            pass

    def _start_tool(self, event: Any) -> None:
        """Open a held-open ``tool`` span for a ``tool_start`` event."""
        name = _tool_name(getattr(event, "tool", None))
        args = _stringify(getattr(event, "arguments", None))
        run = self._trace.open_span(
            name=name or "tool",
            run_type="tool",
            inputs={"arguments": args},
        )
        self._open_tools.setdefault((name, args), []).append(run)

    def _end_tool(self, event: Any, received_at: float) -> None:
        """Close the matching open tool span for a ``tool_end`` event.

        Matched on ``(tool_name, arguments)`` FIFO. If no open start matches
        (e.g. tracing began mid-call), fall back to a point-in-time tool span so
        the call is still recorded.
        """
        name = _tool_name(getattr(event, "tool", None))
        args = _stringify(getattr(event, "arguments", None))
        output = _stringify(getattr(event, "output", None))
        queue = self._open_tools.get((name, args))
        if queue:
            run = queue.pop(0)
            if not queue:
                del self._open_tools[(name, args)]
            self._trace.close_span(run, outputs={"output": output})
            return
        with self._trace.event_span(
            {"tool": name, "arguments": args, "output": output},
            received_at,
            name=name or "tool",
            run_type="tool",
            inbound=False,
            inputs={"arguments": args},
            outputs={"output": output},
        ):
            pass

    def flush_pending(self) -> None:
        """Emit any messages still pending and close orphaned tool spans.

        Called at teardown. A ``tool_start`` whose tool raised (or a session torn
        down mid-call) never gets a ``tool_end``; those spans are closed here with
        an error so they don't dangle open forever.
        """
        self._flush(hold_last=False)
        for queue in self._open_tools.values():
            for run in queue:
                run.error = "tool did not complete before the session ended"
                self._trace.close_span(run)
        self._open_tools.clear()

    def _observe_items(self, seq: list[tuple], received_at: float) -> None:
        """Fold ``(item_id, role, text)`` tuples into the map.

        A brand-new user item begins a turn: the previous turn's messages are
        flushed first (so they stay grouped under it), then a new turn opens and
        the latency timer is armed.
        """
        for iid, role, text in seq:
            if not iid:
                continue
            if iid not in self._items and role == "user":
                self._flush(hold_last=False)
                self._trace.start_turn()
                self._latency_since = received_at
            cur = self._items.get(iid)
            if cur is None:
                self._items[iid] = {"role": role, "text": text}
            else:
                if role:
                    cur["role"] = role
                if text:  # latest non-empty text wins → collapses partials
                    cur["text"] = text
            if role in ("user", "assistant") and text:
                self._notify(role, text)

    def _flush(self, hold_last: bool) -> None:
        """Emit not-yet-emitted items in order.

        Optionally holds back the last (still-streaming) item until it is
        superseded or the session ends.
        """
        ids = list(self._items)
        cutoff = len(ids) - 1 if hold_last else len(ids)
        for iid in ids[: max(0, cutoff)]:
            if iid not in self._emitted:
                self._record_item(iid)

    def record_first_audio(self, received_at: float) -> None:
        """Record ``latency_to_first_audio_ms`` on the open turn, once per turn."""
        if self._latency_since is not None:
            self._trace.add_turn_metadata(
                latency_to_first_audio_ms=round(
                    (received_at - self._latency_since) * 1000
                )
            )
            self._latency_since = None

    def _notify(self, role: str | None, text: str | None) -> None:
        """Send one finalized transcript line to the on_message callback once."""
        if self._on_message is None or not role or not text:
            return
        if (role, text) in self._notified:
            return
        self._notified.add((role, text))
        self._on_message(role, text)

    def _record_item(self, iid: str) -> None:
        """Emit one message span for a finalized history item (once)."""
        role = self._items[iid]["role"]
        text = (self._items[iid]["text"] or "").strip()
        if role not in ("user", "assistant"):
            self._emitted.add(iid)  # tool/system items are never messages
            return
        if not text:
            return  # text not in yet (may arrive late, e.g. a barge-in) — pending
        self._emitted.add(iid)
        self._notify(role, text)
        self._trace.add_message(role, text)
        if role == "user":
            with self._trace.event_span(
                {"item_id": iid, "role": "user", "content": text},
                self._trace.now(),
                name="user_message",
                inbound=True,
                inputs={"role": "user", "content": text},
            ):
                pass
        else:
            self._trace.record_llm(
                outputs={"role": "assistant", "content": text},
                metadata={"ls_provider": "openai", "ls_model_name": self._model},
            )


class _TracedRealtimeSession:
    """Async-context-manager proxy over a ``RealtimeSession`` that traces events.

    Delegates the underlying session's ``async with`` and every attribute
    (``send_audio``, …), iterates its events, and observes each. On exit it emits
    any pending messages and finalizes the conversation root (transcript + WAV).
    Exposes ``record_user_audio`` / ``record_agent_audio`` for the stereo WAV.
    """

    def __init__(
        self,
        session: Any,
        *,
        thread_id: Optional[str],
        sample_rate: int,
        project_name: Optional[str],
        tags: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
        on_message: Optional[Callable[[str, str], None]],
        max_audio_seconds: Optional[float],
        client: Optional[Client],
        replicas: Optional[Sequence[WriteReplica]],
    ) -> None:
        # Plain assignment is safe: this proxy only overrides ``__getattr__``
        # (read miss) — not ``__setattr__`` — so writes never delegate.
        self._session = session
        self._thread_id = thread_id or str(uuid.uuid4())
        self._sample_rate = sample_rate
        self._project_name = project_name
        self._tags = tags
        self._metadata = metadata
        self._on_message = on_message
        self._max_audio_seconds = max_audio_seconds
        self._client = client
        self._replicas = replicas
        # Created lazily in ``__aenter__``; annotate so their real types are
        # known despite the ``None`` seed.
        self._trace: Optional[EventSession] = None
        self._tracer: Optional[_AgentsRealtimeTracer] = None
        self._ctx: Any = None
        self._aiter: Any = None

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_session"), name)

    async def __aenter__(self) -> _TracedRealtimeSession:
        await self._session.__aenter__()
        # The underlying session is now open. If our own tracing setup raises,
        # Python won't call __aexit__ (the context was never successfully
        # entered), so we must unwind the session here or it leaks.
        try:
            trace = start_session(
                thread_id=self._thread_id,
                sample_rate=self._sample_rate,
                project_name=self._project_name,
                tags=self._tags,
                metadata=self._metadata,
                max_audio_seconds=self._max_audio_seconds,
                client=self._client,
                replicas=self._replicas,
                integration="openai-agents-realtime",
                integration_version=get_package_version("openai-agents"),
            )
            self._trace = trace
            ctx = tracing_context(
                metadata={"thread_id": self._thread_id},
                tags=self._tags,
                project_name=self._project_name,
                replicas=self._replicas,
            )
            ctx.__enter__()
            self._ctx = ctx
            self._tracer = _AgentsRealtimeTracer(
                trace, on_message=self._on_message, model=_resolve_model(self._session)
            )
        except BaseException:
            if self._ctx is not None:
                try:
                    self._ctx.__exit__(*sys.exc_info())
                except Exception:
                    logger.debug(
                        "voice tracing: error unwinding context after a failed "
                        "session enter",
                        exc_info=True,
                    )
            await self._session.__aexit__(*sys.exc_info())
            raise
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        # Teardown is best-effort: closing the trace must neither mask the
        # caller's exception nor stop the underlying session from being exited.
        # The tracing context is always restored (``finally``) so it can't leak.
        try:
            if self._tracer is not None:
                self._tracer.flush_pending()
            if self._trace is not None:
                if exc is not None:
                    self._trace.run.error = f"{exc_type.__name__}: {exc}"
                self._trace.finalize()
        except Exception:
            logger.warning("voice tracing: failed to finalize session", exc_info=True)
        finally:
            if self._ctx is not None:
                self._ctx.__exit__(None, None, None)
        return await self._session.__aexit__(exc_type, exc, tb)

    def __aiter__(self) -> _TracedRealtimeSession:
        self._aiter = self._session.__aiter__()
        return self

    async def __anext__(self) -> Any:
        aiter = self._aiter
        if aiter is None:
            aiter = self._session.__aiter__()
            self._aiter = aiter
        event = await aiter.__anext__()
        if self._tracer is not None:
            observe_safely(self._tracer.observe, event)
        return event

    def record_user_audio(self, pcm: bytes) -> None:
        """Record a chunk of user (mic) PCM16 for the stereo conversation WAV."""
        if self._trace is not None:
            self._trace.record_user(self._trace.now(), pcm)

    def record_agent_audio(self, pcm: bytes) -> None:
        """Record a chunk of agent (played) PCM16 for the stereo conversation WAV."""
        if self._trace is not None:
            self._trace.record_agent(self._trace.now(), pcm)


def wrap_realtime_session(
    session: Any,
    *,
    thread_id: Optional[str] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    on_message: Optional[Callable[[str, str], None]] = None,
    max_audio_seconds: Optional[float] = None,
    client: Optional[Client] = None,
    replicas: Optional[Sequence[WriteReplica]] = None,
) -> _TracedRealtimeSession:
    """Trace an OpenAI Agents SDK ``RealtimeSession`` into LangSmith.

    Returns an async-context-manager proxy that also enters the underlying
    session; iterate and call it exactly as you would the original::

        session = await runner.run()
        async with wrap_realtime_session(session, thread_id=tid) as conn:
            async for event in conn:
                ...

    To capture the stereo conversation WAV, feed PCM via the proxy's
    ``record_user_audio`` / ``record_agent_audio``.

    Args:
        session: the ``RealtimeSession`` returned by ``RealtimeRunner.run()``.
        thread_id: LangSmith thread id; a random UUID if omitted.
        sample_rate: PCM sample rate of the audio (for the WAV).
        project_name: LangSmith project; defaults to standard ``LANGSMITH_*`` config.
        tags / metadata: attached to the conversation root span.
        on_message: optional callback ``(role, text)`` invoked once per finalized
            transcript line (e.g. to print to a console).
        max_audio_seconds: per-channel cap on audio retained for the WAV, to
            bound memory on long sessions; ``None`` (default) keeps all audio.
        client: LangSmith ``Client`` for tracing writes; ``None`` (default) uses
            the SDK's standard env-based resolution (``LANGSMITH_*``).
        replicas: tracing replicas to mirror the conversation trace to additional
            destinations; ``None`` (default) disables replication.
    """
    return _TracedRealtimeSession(
        session,
        thread_id=thread_id,
        sample_rate=sample_rate,
        project_name=project_name,
        tags=tags,
        metadata=metadata,
        on_message=on_message,
        max_audio_seconds=max_audio_seconds,
        client=client,
        replicas=replicas,
    )
