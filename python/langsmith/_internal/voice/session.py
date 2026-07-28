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

import logging
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from langsmith import RunTree
from langsmith._internal.voice.audio import (
    DEFAULT_MAX_AUDIO_SECONDS,
    build_stereo_session_wav,
    session_wav_exceeds_duration_cap,
)
from langsmith._internal.voice.helpers import dump_event, scrub

if TYPE_CHECKING:
    from langsmith import Client
    from langsmith.run_trees import WriteReplica

logger = logging.getLogger(__name__)

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
    # Per-channel cap on retained PCM, in bytes. Audio is buffered in memory for
    # the whole conversation, so without a ceiling a long-running session grows
    # unbounded (a 1h 24kHz/16-bit channel is ~170MB). Once a channel hits this,
    # further chunks on it are dropped (the conversation's start is kept) and the
    # root is flagged ``audio_truncated``. ``None`` disables the cap.
    max_audio_bytes: Optional[int] = None
    max_audio_seconds: Optional[float] = DEFAULT_MAX_AUDIO_SECONDS
    # Monotonic clock origin. Everything else stores ``now() - t0``.
    t0: float = field(default_factory=time.monotonic)
    # Time-stamped audio chunks for the stereo session WAV. Each entry is
    # (offset_seconds_from_t0, pcm16_bytes). Reconstructed at finalize.
    user_chunks: list[tuple[float, bytes]] = field(default_factory=list)
    agent_chunks: list[tuple[float, bytes]] = field(default_factory=list)
    # Running per-channel byte totals, checked against ``max_audio_bytes``.
    _user_bytes: int = field(default=0, init=False)
    _agent_bytes: int = field(default=0, init=False)
    _audio_truncated: bool = field(default=False, init=False)
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
    # Whether the root has been named from an utterance yet (see ``set_title``).
    _title_set: bool = field(default=False, init=False)

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
        """Record a timestamped chunk of user (mic) PCM16 for the stereo WAV.

        Dropped once the user channel reaches ``max_audio_bytes`` (see that
        field) so a long session can't exhaust memory.
        """
        chunk = self._bounded_audio_chunk(self._user_bytes, data)
        if not chunk:
            return
        self._user_bytes += len(chunk)
        self.user_chunks.append((t, chunk))

    def record_agent(self, t: float, data: bytes) -> None:
        """Record a timestamped chunk of agent (playback) PCM16 for the WAV.

        Dropped once the agent channel reaches ``max_audio_bytes`` (see that
        field) so a long session can't exhaust memory.
        """
        chunk = self._bounded_audio_chunk(self._agent_bytes, data)
        if not chunk:
            return
        self._agent_bytes += len(chunk)
        self.agent_chunks.append((t, chunk))

    def _bounded_audio_chunk(self, current_bytes: int, data: bytes) -> bytes:
        if self.max_audio_bytes is None:
            return data
        remaining = self.max_audio_bytes - current_bytes
        remaining -= remaining % 2
        if remaining <= 0:
            self._note_audio_truncated()
            return b""
        if len(data) <= remaining:
            return data
        self._note_audio_truncated()
        return data[:remaining]

    def _note_audio_truncated(self) -> None:
        """Flag once that recorded audio was capped."""
        if self._audio_truncated:
            return
        self._audio_truncated = True
        logger.warning(
            "voice tracing: audio capture hit the configured cap; "
            "further audio for this conversation is dropped from the WAV"
        )

    def set_title(self, text: str) -> None:
        """Name the conversation root from its first user utterance (first wins).

        The root's ``name`` is what LangSmith shows in the trace / threads list,
        so naming it after the opening utterance makes conversations scannable
        instead of all reading ``realtime_session``. Only the first non-empty
        utterance applies; scrubbed like any other payload. The new name rides
        along on the root's ``patch`` at ``finalize``.
        """
        text = (text or "").strip()
        if not text or self._title_set:
            return  # first non-empty user utterance wins
        self.run.name = cast("str", scrub(text))
        self._title_set = True

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

        ``usage_metadata`` must be passed here, not patched on afterwards: cost
        is derived when the run is finalized, so usage that lands on a later
        patch (after ``end``) is not reflected. Services that report tokens on a
        separate, later event should defer this call until the counts arrive.
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

    def open_span(
        self,
        *,
        name: str,
        run_type: RunKind = "chain",
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunTree:
        """Open a child span and return it for the caller to ``close_span`` later.

        Unlike ``event_span`` (a context manager that fixes its ``outputs`` up
        front), this is for work whose result is only known at a *later* event —
        e.g. a tool call that spans a ``tool_start``/``tool_end`` pair, where the
        wall-clock gap between the two events is the real tool latency. Nests
        under the current turn (or the root) and counts toward ``event_count``,
        like any other event span. The caller must pair every ``open_span`` with
        a ``close_span`` (see the adapters' teardown, which closes any that were
        left open).
        """
        self.event_count += 1
        parent = self._current_turn or self.run
        run = parent.create_child(
            name=name,
            run_type=run_type,
            inputs=scrub(inputs) if inputs is not None else {},
            tags=["event"],
            extra={"metadata": metadata or {}},
        )
        run.post()
        return run

    def close_span(
        self,
        run: RunTree,
        *,
        outputs: dict[str, Any] | None = None,
        usage_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End and patch a span previously opened with ``open_span``.

        Any error already set on ``run`` (``run.error``) is preserved. Outputs
        pass through ``scrub`` like every other span payload. ``metadata`` is
        merged into the run's existing metadata at close — for detail only known
        when the span ends (e.g. the raw wire payload of the event that closed
        it), so an ``open_span`` span can preserve it the way ``event_span``
        does. It passes through ``scrub`` like any other payload.
        """
        if usage_metadata is not None:
            run.set(usage_metadata=cast("Any", usage_metadata))
        if metadata:
            extra = run.extra or {}
            merged = dict(extra.get("metadata") or {})
            merged.update(scrub(metadata))
            extra["metadata"] = merged
            run.extra = extra
        run.end(outputs=scrub(outputs) if outputs is not None else {})
        run.patch()

    def _audio_exceeds_duration_cap(self) -> bool:
        return session_wav_exceeds_duration_cap(
            self.user_chunks,
            self.agent_chunks,
            self.sample_rate,
            self.max_audio_seconds,
        )

    def finalize(self) -> None:
        """Roll up stats, attach the stereo WAV, and close the root span.

        Best-effort: a failure building the WAV must not stop the root span from
        being closed, and finalize as a whole must not raise into the caller's
        teardown (see the adapters' ``__aexit__``).
        """
        # Close the last open turn (if any) before the root.
        self._close_turn()
        if self._audio_exceeds_duration_cap():
            self._note_audio_truncated()
        extra: dict[str, Any] = self.run.extra or {}
        metadata: dict[str, Any] = dict(extra.get("metadata") or {})
        metadata["event_count"] = self.event_count
        metadata["duration_s"] = round(time.monotonic() - self.t0, 2)
        if self._audio_truncated:
            metadata["audio_truncated"] = True
        extra["metadata"] = metadata
        self.run.extra = extra

        try:
            wav = build_stereo_session_wav(
                self.user_chunks,
                self.agent_chunks,
                self.sample_rate,
                max_duration_seconds=self.max_audio_seconds,
            )
        except Exception:
            # A WAV-build failure (e.g. an oversized buffer) must not lose the
            # rest of the trace — drop the audio asset and close the root.
            logger.warning("voice tracing: failed to build session WAV", exc_info=True)
            wav = b""
        if wav:
            # One audio asset for the whole conversation — stereo so you can
            # hear both sides AND see interruption overlap.
            # ``(mime_type, bytes)`` is a valid attachment; the ignore is for
            # mypy's invariant-dict-value false positive on the union type.
            self.run.attachments = {  # type: ignore[assignment]
                "conversation": ("audio/wav", wav)
            }
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
    max_audio_seconds: Optional[float] = DEFAULT_MAX_AUDIO_SECONDS,
    client: Optional[Client] = None,
    replicas: Optional[Sequence[WriteReplica]] = None,
    integration: str,
    integration_version: Optional[str] = None,
) -> EventSession:
    """Create and post the conversation root span, returning an ``EventSession``.

    ``project_name`` falls back to LangSmith's standard resolution
    (``LANGSMITH_PROJECT``) when omitted, like any other ``RunTree``.

    ``client`` is an optional LangSmith ``Client`` for all tracing writes; child
    spans inherit it via ``create_child``. ``None`` uses the SDK's standard
    env-based client resolution.

    ``replicas`` mirrors the conversation trace to additional destinations
    (see LangSmith's tracing replicas). Set on the root and inherited by child
    spans via ``create_child``; ``None`` disables replication.

    ``max_audio_seconds`` caps how much audio per channel is retained and how far
    into the session the stereo WAV can extend, guarding memory on long-running
    sessions. The default is bounded; pass ``None`` to keep all audio. It is
    converted to a per-channel byte budget at PCM16 (2 bytes/sample).

    ``integration`` / ``integration_version`` stamp ``ls_integration`` and
    ``ls_integration_version`` on the root (the convention the batch integrations
    use) so LangSmith can attribute the trace to a specific integration and the
    framework version in use. Set authoritatively — a caller cannot shadow them
    via ``metadata``. ``integration_version`` may be ``None`` when the framework
    version can't be resolved.
    """
    # Mark the root as an audio-modality run (these are voice conversations).
    # Integration attribution comes after ``**metadata`` so it wins — a caller
    # can't shadow ls_integration via their own metadata.
    md = {
        "ls_modality": "audio",
        "thread_id": thread_id,
        **(metadata or {}),
        "ls_integration": integration,
        "ls_integration_version": integration_version,
    }
    # ``RunTree.session_name`` (aliased ``project_name``) is a ``str`` with a
    # default factory; passing ``None`` explicitly fails validation, so only
    # forward it when set and let the SDK resolve ``LANGSMITH_PROJECT`` otherwise.
    project_kwargs = {"project_name": project_name} if project_name is not None else {}
    # Only forward an explicit client; omit it so ``RunTree`` keeps its standard
    # env-based resolution when the caller didn't supply one.
    client_kwargs = {"client": client} if client is not None else {}
    run = RunTree(
        name=name,
        run_type="chain",
        inputs={},
        tags=tags or [],
        extra={"metadata": md},
        replicas=replicas,
        **project_kwargs,
        **client_kwargs,
    )
    run.post()
    max_audio_bytes = (
        int(max_audio_seconds * sample_rate * 2)
        if max_audio_seconds is not None
        else None
    )
    return EventSession(
        run=run,
        thread_id=thread_id,
        project_name=project_name,
        sample_rate=sample_rate,
        max_audio_bytes=max_audio_bytes,
        max_audio_seconds=max_audio_seconds,
    )
