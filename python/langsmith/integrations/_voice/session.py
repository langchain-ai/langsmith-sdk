"""``EventSession`` — Track B's LangSmith ``RunTree`` builder.

The integrations that observe a remote event stream (OpenAI Realtime, OpenAI
Agents realtime, ADK Live) all face the same problem: the service hands them an
event stream rather than emitting its own telemetry for the live loop, so the
trace has to be built by hand with the LangSmith SDK — one root span per
conversation, one child span per meaningful event.

``EventSession`` is everything that pattern needs and would otherwise be
duplicated across the adapters:

* a root ``realtime_session`` span carrying the running transcript (``outputs``)
  and the stereo conversation WAV (attachment);
* a child span per event (``event_span``), optionally grouped into ``turn``
  spans;
* point-in-time ``llm`` spans for terminal model responses (``record_llm``);
* timestamped audio recording and a ``finalize`` that rolls up stats + WAV.

Each adapter keeps only what is genuinely provider-specific: which events count
as ``inbound`` (user→model, so the payload lands in span ``inputs``) and how to
label each event span.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

from langsmith import RunTree

from .audio import build_stereo_session_wav, dump_event, scrub

# The run kinds LangSmith recognizes (matches ``RunTree.create_child``).
RunKind = Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]


@dataclass
class EventSession:
    """Conversation-level tracing state. One per conversation.

    The root span carries roll-up stats in metadata, the running conversation
    transcript as its ``outputs`` (so the LangSmith preview pane shows the whole
    exchange at a glance — see ``add_message``), and the stereo conversation WAV
    as an attachment. Each received event becomes a child span via
    ``event_span`` — nested under the current ``turn`` span if the adapter opted
    into turn grouping (see ``start_turn``), otherwise directly under the root.
    """

    run: RunTree
    thread_id: str
    project_name: Optional[str]
    sample_rate: int
    # Monotonic clock origin. Everything else stores ``now() - t0``.
    t0: float = field(default_factory=time.monotonic)
    # Time-stamped audio chunks for the stereo session WAV. Each entry is
    # (offset_seconds_from_t0, pcm16_bytes). Reconstructed at finalize.
    user_chunks: list[tuple[float, bytes]] = field(default_factory=list)
    agent_chunks: list[tuple[float, bytes]] = field(default_factory=list)
    event_count: int = 0
    # Conversation transcript, in turn order: {"role", "content"} per line.
    # Surfaced as the root span's ``outputs`` at finalize.
    messages: list[dict[str, str]] = field(default_factory=list)
    # Optional turn grouping (see ``start_turn``). When a turn is open, event
    # spans nest under it instead of directly under the root; adapters that
    # never call ``start_turn`` get the original flat shape unchanged.
    _current_turn: RunTree | None = field(default=None, init=False)
    _turn_count: int = field(default=0, init=False)
    _turn_msg_start: int = field(default=0, init=False)

    def now(self) -> float:
        """Seconds since the session started — the timeline used for the WAV."""
        return time.monotonic() - self.t0

    def start_turn(self) -> None:
        """Open a new conversational-turn span, closing the previous one.

        Subsequent ``event_span`` calls nest under this turn until the next
        ``start_turn`` (or ``finalize``). The turn's ``outputs`` become the
        transcript lines added during it, so each turn previews its own
        exchange. Opt-in: an adapter that never calls this keeps the flat root
        layout.
        """
        self._close_turn()
        self._turn_count += 1
        self._turn_msg_start = len(self.messages)
        turn = self.run.create_child(
            name="turn",
            run_type="chain",
            inputs={},
            tags=["turn"],
            extra={"metadata": {"turn": self._turn_count}},
        )
        turn.post()
        self._current_turn = turn

    def _close_turn(self) -> None:
        """End the currently open turn span, if any, with its transcript."""
        if self._current_turn is None:
            return
        msgs = self.messages[self._turn_msg_start :]
        self._current_turn.end(outputs={"messages": msgs} if msgs else {})
        self._current_turn.patch()
        self._current_turn = None

    def add_message(self, role: str, content: str) -> None:
        """Append one transcript line to the conversation rollup.

        Empty/whitespace content is ignored (failed transcriptions, silent
        turns). Content is truncated like any other span payload (see ``scrub``)
        so an unexpectedly large blob never bloats the root span.
        """
        content = (content or "").strip()
        if content:
            self.messages.append({"role": role, "content": scrub(content)})

    def record_user(self, t: float, data: bytes) -> None:
        """Record a timestamped chunk of user (mic) PCM16 for the stereo WAV."""
        self.user_chunks.append((t, data))

    def record_agent(self, t: float, data: bytes) -> None:
        """Record a timestamped chunk of agent (playback) PCM16 for the WAV."""
        self.agent_chunks.append((t, data))

    def set_title(self, text: str) -> None:
        """Give the conversation root a human-readable title (first one wins).

        Set from the first user utterance so traces are scannable in the project
        / threads list instead of all reading ``realtime_session``. Scrubbed
        like any other payload.
        """
        text = (text or "").strip()
        if not text:
            return
        extra = self.run.extra or {}
        metadata = dict(extra.get("metadata") or {})
        if metadata.get("title"):
            return  # first non-empty user utterance wins
        metadata["title"] = scrub(text)
        extra["metadata"] = metadata
        self.run.extra = extra

    def add_turn_metadata(self, **kv: Any) -> None:
        """Merge key/values into the open turn span's metadata (no-op if none).

        For per-turn metrics not known when the turn opens — e.g.
        ``latency_to_first_audio_ms``, ``was_interrupted``. Applied to the
        currently open turn, so call it before the next ``start_turn`` closes
        that turn.
        """
        if self._current_turn is None:
            return
        extra = self._current_turn.extra or {}
        metadata = dict(extra.get("metadata") or {})
        metadata.update(kv)
        extra["metadata"] = metadata
        self._current_turn.extra = extra

    @contextmanager
    def event_span(
        self,
        event: Any,
        t_now: float,
        *,
        name: str,
        inbound: bool,
        run_type: RunKind = "chain",
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[RunTree]:
        """Open a child span for one received event; close it on body exit.

        Wrapping the handler body means any real work done while handling the
        event (e.g. tool execution) nests inside this span — the same way a tool
        call nests under the step that triggered it in any traced app.

        By default the raw (scrubbed) event payload is the span's I/O — in
        ``inputs`` for user→model (``inbound``) events, in ``outputs`` otherwise.
        Pass curated ``inputs``/``outputs`` (and optionally a ``run_type`` like
        "llm" plus ``usage_metadata``) to give the span readable,
        conversation-shaped I/O instead; the full wire payload is then preserved
        under ``metadata.raw_event``. Curated values pass through ``scrub`` too,
        so no un-scrubbed event data ever reaches a span.
        """
        self.event_count += 1
        payload = scrub(dump_event(event))
        # "Curated" = the caller supplied readable I/O or a non-default kind, so
        # the raw wire payload is demoted to metadata rather than the headline.
        curated = inputs is not None or outputs is not None or run_type != "chain"

        md: dict[str, Any] = {"received_at_s": round(t_now, 3)}
        if curated:
            md["raw_event"] = payload
        if metadata:
            md.update(metadata)

        if inputs is not None:
            run_inputs: Any = scrub(inputs)
        elif curated:
            run_inputs = {}
        else:
            run_inputs = payload if inbound else {}

        parent = self._current_turn or self.run
        run = parent.create_child(
            name=name,
            run_type=run_type,
            inputs=run_inputs,
            tags=["event"],
            extra={"metadata": md},
        )
        run.post()
        try:
            yield run
        finally:
            if usage_metadata is not None:
                run.set(usage_metadata=cast("Any", usage_metadata))
            if curated:
                run.end(outputs=scrub(outputs) if outputs is not None else {})
            else:
                run.end(outputs={} if inbound else payload)
            run.patch()

    def record_llm(
        self,
        parent: RunTree | None = None,
        *,
        name: str = "model",
        outputs: dict[str, Any],
        inputs: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a point-in-time ``llm`` child span for a model response.

        Voice services deliver a response as a *terminal* event (e.g. Realtime's
        ``response.done``), so there's no model-inference duration to measure —
        but the token usage, assistant message, and finish status still belong
        on an ``llm``-kind run for cost rollup and readability. Kept
        point-in-time and separate from the surrounding handler span so local
        tool latency is never attributed to the model call. ``parent`` defaults
        to the current turn (or the root).

        When ``inputs`` is omitted, it defaults to the model's *effective
        prompt* — the conversation transcript so far minus the response being
        recorded (the trailing assistant message) — so the ``llm`` run reads like
        a normal model call instead of having empty inputs.
        """
        parent = parent or self._current_turn or self.run
        if inputs is None:
            context = list(self.messages)
            if context and context[-1].get("role") == "assistant":
                context = context[:-1]  # drop the response we're recording
            inputs = {"messages": context}
        run = parent.create_child(
            name=name,
            run_type="llm",
            inputs=scrub(inputs),
            tags=["model"],
            extra={"metadata": metadata or {}},
        )
        run.post()
        if usage_metadata is not None:
            run.set(usage_metadata=cast("Any", usage_metadata))
        run.end(outputs=scrub(outputs))
        run.patch()

    def finalize(self) -> None:
        """Roll up stats, attach the stereo WAV, and close the root span."""
        # Close the last open turn (if any) before the root.
        self._close_turn()
        extra: dict[str, Any] = self.run.extra or {}
        metadata: dict[str, Any] = dict(extra.get("metadata") or {})
        metadata["event_count"] = self.event_count
        metadata["duration_s"] = round(time.monotonic() - self.t0, 2)
        extra["metadata"] = metadata
        self.run.extra = extra

        wav = build_stereo_session_wav(
            self.user_chunks, self.agent_chunks, self.sample_rate
        )
        if wav:
            # One audio asset for the whole conversation — stereo so you can
            # hear both sides AND see interruption overlap.
            self.run.attachments = {"conversation": ("audio/wav", wav)}
        # The transcript is the conversation's natural "output": surfacing it on
        # the root makes the whole exchange readable in the LangSmith preview
        # pane without expanding a single child span.
        self.run.end(outputs={"messages": self.messages} if self.messages else {})
        self.run.patch()


def start_session(
    *,
    thread_id: str,
    sample_rate: int,
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    name: str = "realtime_session",
) -> EventSession:
    """Create and post the conversation root span, returning an ``EventSession``.

    ``project_name`` falls back to LangSmith's standard resolution
    (``LANGSMITH_PROJECT``) when omitted, like any other ``RunTree``.
    """
    # Mark the root as an audio-modality run (these are voice conversations).
    md = {"ls_modality": "audio", "thread_id": thread_id, **(metadata or {})}
    run = RunTree(
        name=name,
        run_type="chain",
        inputs={},
        project_name=project_name,
        tags=tags or [],
        extra={"metadata": md},
    )
    run.post()
    return EventSession(
        run=run,
        thread_id=thread_id,
        project_name=project_name,
        sample_rate=sample_rate,
    )
