"""LangSmith tracing for Google ADK Live (``Runner.run_live``).

ADK emits ``gen_ai.*`` OTel spans for its non-live paths, but ``run_live`` — the
whole voice loop — isn't instrumented, so an OTel-only setup yields an empty
root. This integration builds the trace from the live event stream instead,
using ADK's official plugin hook: :class:`LangSmithLivePlugin` is a
``BasePlugin`` whose ``before_run`` / ``on_event`` / ``after_run`` callbacks open
the conversation root span, span each meaningful event, and finalize.

The plugin runs alongside the application's own ``run_live`` loop (which plays
audio and reacts to barge-ins) — it carries no application logic. Audio for the
stereo conversation WAV is fed by the app via :meth:`record_user_audio` /
:meth:`record_agent_audio` (recording at the speaker/mic boundary captures what
was actually *heard*, post-barge-in-truncation — more accurate than the audio
embedded in events).

Trace shape — one conversation = one trace::

    realtime_session                       (root; transcript + stereo WAV)
    ├── input_transcription                (event — user speech)
    ├── function_call: get_weather         (event)
    ├── function_response: get_weather     (event)
    ├── output_transcription               (event — agent speech)
    ├── turn_complete                      (event)
    └── interrupted                        (event)
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Optional

from google.adk.plugins.base_plugin import BasePlugin

from .._voice.session import EventSession, start_session

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

    @property
    def is_audio_only(self) -> bool:
        """True when the event's only payload is agent audio (a flood — not spanned)."""
        return bool(self.audio_chunks) and not (
            self.interrupted
            or self.turn_complete
            or self.user_transcript
            or self.agent_transcript
            or self.function_calls
            or self.function_responses
        )

    @property
    def is_inbound(self) -> bool:
        return self.user_transcript is not None

    @property
    def label(self) -> str:
        if self.interrupted:
            return "interrupted"
        if self.turn_complete:
            return "turn_complete"
        if self.user_transcript:
            return "input_transcription"
        if self.agent_transcript:
            return "output_transcription"
        if self.function_calls:
            return f"function_call: {self.function_calls[0].name}"
        if self.function_responses:
            return f"function_response: {self.function_responses[0].name}"
        return "event"


class LangSmithLivePlugin(BasePlugin):
    """An ADK ``BasePlugin`` that traces ``run_live`` conversations to LangSmith.

    Register it on the ``Runner`` (``Runner(..., plugins=[plugin])``). One run =
    one trace. Feed audio via :meth:`record_user_audio` / :meth:`record_agent_audio`
    to attach the stereo conversation WAV.
    """

    def __init__(
        self,
        *,
        name: str = "langsmith_live",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
        project_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Create the plugin.

        Args:
            name: plugin name (required by ``BasePlugin``).
            sample_rate: PCM sample rate of the audio (for the WAV).
            thread_id_provider: zero-arg callable returning the LangSmith thread
                id for the run; a random UUID per run if omitted.
            project_name: LangSmith project; defaults to standard config.
            tags / metadata: attached to the conversation root span.
        """
        super().__init__(name=name)
        self._sample_rate = sample_rate
        self._thread_id_provider = thread_id_provider
        self._project_name = project_name
        self._tags = tags
        self._metadata = metadata
        self._session: EventSession | None = None

    # -- app-fed audio --------------------------------------------------------

    def record_user_audio(self, pcm: bytes) -> None:
        """Record a chunk of user (mic) PCM16 for the stereo conversation WAV."""
        if self._session is not None:
            self._session.record_user(self._session.now(), pcm)

    def record_agent_audio(self, pcm: bytes) -> None:
        """Record a chunk of agent (played) PCM16 for the stereo conversation WAV."""
        if self._session is not None:
            self._session.record_agent(self._session.now(), pcm)

    # -- ADK plugin callbacks -------------------------------------------------

    async def before_run_callback(self, *, invocation_context: Any) -> None:
        thread_id = (
            self._thread_id_provider() if self._thread_id_provider else None
        ) or str(uuid.uuid4())
        self._session = start_session(
            thread_id=thread_id,
            sample_rate=self._sample_rate,
            project_name=self._project_name,
            tags=self._tags,
            metadata=self._metadata,
        )

    async def on_event_callback(self, *, invocation_context: Any, event: Any) -> None:
        if self._session is None:
            return
        view = _LiveEventView(event)
        if view.is_audio_only:
            return  # the agent-audio flood: played by the app, not spanned

        # Roll the finalized transcripts into the root preview / title.
        if view.final_user_transcript:
            self._session.add_message("user", view.final_user_transcript)
            self._session.set_title(view.final_user_transcript)
        if view.final_agent_transcript:
            self._session.add_message("assistant", view.final_agent_transcript)

        with self._session.event_span(
            event, self._session.now(), name=view.label, inbound=view.is_inbound
        ):
            pass

    async def after_run_callback(self, *, invocation_context: Any) -> None:
        """Finalize the conversation trace (attach the transcript and audio).

        Idempotent, so it is safe if ADK invokes it more than once.
        """
        session, self._session = self._session, None
        if session is not None:
            session.finalize()
