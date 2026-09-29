"""LangSmith tracing for a raw Gemini Live WebSocket session.

Gemini Live is exposed by ``google-genai`` as an ``AsyncSession`` over a
bidirectional WebSocket. :func:`wrap_gemini_live` returns a transparent proxy
whose :meth:`receive` generator observes each ``LiveServerMessage`` while
leaving the application's own audio playback and tool loop untouched.

Trace shape -- one live session = one trace::

    realtime_session                         (root; transcript + stereo WAV)
    ├── input_transcription                  (curated user message)
    ├── lookup_weather                       (tool; args in / response out)
    ├── turn_complete                        (llm; assistant text + usage)
    ├── interrupted                          (barge-in marker)
    └── turn_complete                        (turn marker)

Provider events are always passed through the shared ``scrub`` helper before
they become span metadata, replacing raw audio bytes and truncating long text.
Tracing is fail-open: observation and teardown failures are logged but never
break the provider session.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from langsmith._internal._package_version import get_package_version
from langsmith._internal.voice.helpers import dump_event, observe_safely, scrub
from langsmith._internal.voice.session import (
    DEFAULT_MAX_AUDIO_SECONDS,
    EventSession,
    start_session,
)
from langsmith.integrations._gemini_usage import normalize_gemini_usage_metadata
from langsmith.run_helpers import tracing_context

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from google.genai.live import AsyncSession
    from google.genai.types import (
        FunctionCall,
        FunctionResponseOrDict,
        LiveServerContent,
        LiveServerMessage,
    )

    from langsmith import Client
    from langsmith.run_trees import RunTree, WriteReplica

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 24_000
MAX_TRANSCRIPT_CHARS = 2_000


class _LiveMessageView:
    """Readable, dependency-free view over a ``LiveServerMessage``."""

    def __init__(self, raw: LiveServerMessage) -> None:
        self.raw = raw

    @property
    def server_content(self) -> LiveServerContent | None:
        return self.raw.server_content

    def _transcript(self, attr: str) -> str | None:
        content = self.server_content
        tx = getattr(content, attr, None) if content is not None else None
        text = getattr(tx, "text", None) if tx is not None else None
        return str(text) if text else None

    @property
    def user_transcript(self) -> str | None:
        return self._transcript("input_transcription")

    @property
    def user_transcript_finished(self) -> bool:
        content = self.server_content
        tx = getattr(content, "input_transcription", None) if content else None
        return bool(tx is not None and getattr(tx, "finished", False))

    @property
    def agent_transcript(self) -> str | None:
        return self._transcript("output_transcription")

    @property
    def function_calls(self) -> list[FunctionCall]:
        tool_call = self.raw.tool_call
        return list(tool_call.function_calls or []) if tool_call is not None else []

    @property
    def cancelled_tool_call_ids(self) -> list[str]:
        cancellation = self.raw.tool_call_cancellation
        return [str(value) for value in cancellation.ids or []] if cancellation else []

    @property
    def interrupted(self) -> bool:
        content = self.server_content
        return bool(content is not None and getattr(content, "interrupted", False))

    @property
    def turn_complete(self) -> bool:
        content = self.server_content
        return bool(content is not None and getattr(content, "turn_complete", False))


def usage_metadata_from_message(
    message: LiveServerMessage,
) -> dict[str, Any] | None:
    """Map Gemini Live usage onto LangSmith's canonical token metadata."""
    return normalize_gemini_usage_metadata(message.usage_metadata)


def _append_transcript(current: str, fragment: str) -> str:
    """Append one Gemini transcription delta, retaining the per-turn cap."""
    remaining = MAX_TRANSCRIPT_CHARS - len(current)
    return current if remaining <= 0 else current + fragment[:remaining]


class _GeminiLiveTracer:
    """Turn raw Gemini Live server messages into a conversation trace."""

    def __init__(
        self,
        session: EventSession,
        *,
        model: str | None,
        is_agent_speaking: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._session = session
        self._model = model
        self._is_agent_speaking = is_agent_speaking
        self._user_text = ""
        self._agent_text = ""
        self._turn_usage: dict[str, Any] | None = None
        self._last_message: LiveServerMessage | None = None
        self._open_tools: dict[str, list[RunTree]] = {}

    def observe(self, message: LiveServerMessage) -> None:
        self._last_message = message
        view = _LiveMessageView(message)
        now = self._session.now()

        if user_fragment := view.user_transcript:
            self._user_text = _append_transcript(self._user_text, user_fragment)
        if view.user_transcript_finished:
            self._flush_user(message, now)

        if agent_fragment := view.agent_transcript:
            self._agent_text = _append_transcript(self._agent_text, agent_fragment)
        usage = usage_metadata_from_message(message)
        if usage is not None:
            self._turn_usage = usage

        if view.interrupted:
            if self._is_agent_speaking is not None and self._is_agent_speaking():
                interruption_metadata = {"was_audible": True}
            else:
                interruption_metadata = None
            with self._session.event_span(
                message,
                now,
                name="interrupted",
                inbound=False,
                outputs={},
                metadata=interruption_metadata,
            ):
                pass

        if view.turn_complete:
            self._flush_user(message, now)
            agent_text = self._take_agent_text()
            if agent_text:
                self._session.add_message("assistant", agent_text)
            with self._session.event_span(
                message,
                now,
                name="turn_complete",
                inbound=False,
                run_type="llm",
                outputs=(
                    {"role": "assistant", "content": agent_text} if agent_text else {}
                ),
                usage_metadata=self._turn_usage,
                metadata={
                    "ls_provider": "google",
                    "ls_model_name": self._model,
                },
            ):
                pass
            self._turn_usage = None

        cancelled_ids = view.cancelled_tool_call_ids
        if cancelled_ids:
            with self._session.event_span(
                message,
                now,
                name="tool_call_cancellation",
                inbound=False,
                outputs={"call_ids": cancelled_ids},
            ):
                pass
            for call_id in cancelled_ids:
                self._cancel_tool(call_id)

        # One held-open tool span per function call. ``send_tool_response`` on
        # the session proxy closes it after the application executes the tool.
        for call in view.function_calls:
            self._start_tool(call, message)

    @staticmethod
    def _field(value: object, name: str) -> object:
        if isinstance(value, Mapping):
            return next((item for key, item in value.items() if key == name), None)
        return getattr(value, name, None)

    @classmethod
    def _tool_id(cls, value: FunctionCall | FunctionResponseOrDict) -> str | None:
        call_id = cls._field(value, "id")
        return call_id if isinstance(call_id, str) else None

    @classmethod
    def _tool_name(cls, value: FunctionCall | FunctionResponseOrDict) -> str | None:
        name = cls._field(value, "name")
        return name if isinstance(name, str) else None

    @classmethod
    def _tool_key(cls, value: FunctionCall | FunctionResponseOrDict) -> str:
        return cls._tool_id(value) or cls._tool_name(value) or "tool"

    def _start_tool(self, call: FunctionCall, message: LiveServerMessage) -> None:
        name = call.name or "tool"
        run = self._session.open_span(
            name=name,
            run_type="tool",
            inputs={"args": call.args},
            metadata={
                "function_call_id": call.id,
                "raw_event": scrub(dump_event(message)),
            },
        )
        self._open_tools.setdefault(self._tool_key(call), []).append(run)

    def observe_tool_responses(
        self,
        responses: FunctionResponseOrDict | Sequence[FunctionResponseOrDict],
    ) -> None:
        """Close tool spans after responses are sent to Gemini."""
        if isinstance(responses, Sequence) and not isinstance(responses, Mapping):
            items = cast("Sequence[FunctionResponseOrDict]", responses)
        else:
            items = (cast("FunctionResponseOrDict", responses),)
        for response in items:
            self._end_tool(response)

    def _end_tool(self, response: FunctionResponseOrDict) -> None:
        name = self._tool_name(response) or "tool"
        response_value = self._field(response, "response")
        outputs = {"response": response_value}
        queue = self._open_tools.get(self._tool_key(response))
        if not queue and self._tool_id(response):
            queue = self._open_tools.get(name)
        if queue:
            run = queue.pop(0)
            self._prune_empty_tools()
            self._session.close_span(
                run,
                outputs=outputs,
                metadata={"raw_response": dump_event(response)},
            )
            return
        with self._session.event_span(
            response,
            self._session.now(),
            name=str(name),
            run_type="tool",
            inbound=False,
            inputs={},
            outputs=outputs,
        ):
            pass

    def _cancel_tool(self, call_id: str) -> None:
        queue = self._open_tools.pop(str(call_id), [])
        for run in queue:
            run.error = "tool call cancelled by Gemini"
            self._session.close_span(run)

    def _prune_empty_tools(self) -> None:
        self._open_tools = {
            key: queue for key, queue in self._open_tools.items() if queue
        }

    def _flush_open_tools(self) -> None:
        for queue in self._open_tools.values():
            for run in queue:
                run.error = "tool did not complete before the session ended"
                self._session.close_span(run)
        self._open_tools.clear()

    def _flush_user(self, message: LiveServerMessage, now: float) -> None:
        text = self._user_text.strip()
        self._user_text = ""
        if not text:
            return
        self._session.add_message("user", text)
        self._session.set_title(text)
        with self._session.event_span(
            message,
            now,
            name="input_transcription",
            inbound=True,
            inputs={"role": "user", "content": text},
        ):
            pass

    def _take_agent_text(self) -> str:
        text = self._agent_text.strip()
        self._agent_text = ""
        return text

    def _flush_incomplete_agent(self) -> None:
        text = self._take_agent_text()
        if not text:
            return
        self._session.add_message("assistant", text)
        self._session.record_llm(
            name="output_transcription",
            outputs={"role": "assistant", "content": text},
            usage_metadata=self._turn_usage,
            metadata={
                "raw_event": scrub(dump_event(self._last_message)),
                "ls_provider": "google",
                "ls_model_name": self._model,
            },
        )
        self._turn_usage = None

    def finalize(self) -> None:
        if self._last_message is not None:
            self._flush_user(self._last_message, self._session.now())
        self._flush_incomplete_agent()
        self._flush_open_tools()


class _TracedGeminiLiveSession:
    """Transparent proxy over ``google.genai.live.AsyncSession``."""

    def __init__(
        self, session: AsyncSession, tracer: _GeminiLiveTracer, trace: EventSession
    ) -> None:
        self._wrapped_session = session
        self._tracer = tracer
        self._trace = trace

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_wrapped_session"), name)

    async def receive(self) -> AsyncIterator[LiveServerMessage]:
        async for message in self._wrapped_session.receive():
            observe_safely(self._tracer.observe, message)
            yield message

    async def send_tool_response(
        self,
        *,
        function_responses: FunctionResponseOrDict | Sequence[FunctionResponseOrDict],
    ) -> None:
        """Forward tool responses and use them to finish inferred tool spans."""
        await self._wrapped_session.send_tool_response(
            function_responses=function_responses
        )
        observe_safely(self._tracer.observe_tool_responses, function_responses)

    def record_user_audio(self, pcm: bytes) -> None:
        """Record user PCM16 for the bounded stereo conversation WAV."""
        self._trace.record_user(self._trace.now(), pcm)

    def record_agent_audio(self, pcm: bytes) -> None:
        """Record actually-played agent PCM16 for the conversation WAV."""
        self._trace.record_agent(self._trace.now(), pcm)


class _GeminiLiveTracingSession:
    """Async context manager that owns one Gemini Live conversation trace."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        model: str | None,
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
        self._wrapped_session = session
        self._model = model
        self._thread_id = thread_id or str(uuid.uuid4())
        self._sample_rate = sample_rate
        self._project_name = project_name
        self._tags = tags
        self._metadata = metadata
        self._is_agent_speaking = is_agent_speaking
        self._max_audio_seconds = max_audio_seconds
        self._client = client
        self._replicas = replicas
        self._trace: EventSession | None = None
        self._tracer: _GeminiLiveTracer | None = None
        self._context: AbstractContextManager[None] | None = None

    async def __aenter__(self) -> _TracedGeminiLiveSession:
        self._trace = start_session(
            thread_id=self._thread_id,
            sample_rate=self._sample_rate,
            project_name=self._project_name,
            tags=self._tags,
            metadata=self._metadata,
            max_audio_seconds=self._max_audio_seconds,
            client=self._client,
            replicas=self._replicas,
            integration="gemini-live",
            integration_version=get_package_version("google-genai"),
        )
        self._context = tracing_context(
            parent=self._trace.run,
            metadata={"thread_id": self._thread_id},
            tags=self._tags,
            project_name=self._project_name,
            replicas=self._replicas,
        )
        self._context.__enter__()
        self._tracer = _GeminiLiveTracer(
            self._trace,
            model=self._model,
            is_agent_speaking=self._is_agent_speaking,
        )
        return _TracedGeminiLiveSession(
            self._wrapped_session, self._tracer, self._trace
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        try:
            if self._tracer is not None:
                self._tracer.finalize()
            if self._trace is not None:
                if exc is not None:
                    self._trace.run.error = f"{type(exc).__name__}: {exc}"
                self._trace.finalize()
        except Exception:
            logger.warning("Gemini Live tracing: failed to finalize", exc_info=True)
        finally:
            if self._context is not None:
                self._context.__exit__(None, None, None)
        return False


def wrap_gemini_live(
    session: AsyncSession,
    *,
    model: str | None = None,
    thread_id: Optional[str] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    is_agent_speaking: Optional[Callable[[], bool]] = None,
    max_audio_seconds: Optional[float] = DEFAULT_MAX_AUDIO_SECONDS,
    client: Optional[Client] = None,
    replicas: Optional[Sequence[WriteReplica]] = None,
) -> _GeminiLiveTracingSession:
    """Trace a Gemini Live ``AsyncSession`` into LangSmith.

    Use the returned async context manager alongside the provider connection::

        async with client.aio.live.connect(model=model, config=config) as raw, \
                   wrap_gemini_live(raw, model=model) as session:
            async for message in session.receive():
                ...

    The yielded object proxies every provider-session method. Feed PCM16 to
    ``record_user_audio`` and ``record_agent_audio`` to attach a bounded stereo
    WAV, and optionally provide ``is_agent_speaking`` to annotate interruptions.
    """
    return _GeminiLiveTracingSession(
        session,
        model=model,
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
