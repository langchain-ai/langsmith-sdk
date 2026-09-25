"""LangSmith tracing for Deepgram's Voice Agent WebSocket protocol.

The Voice Agent API multiplexes JSON control events and raw agent audio over a
single WebSocket. :func:`wrap_deepgram_voice` observes that stream without
changing the application's send/receive loop and builds one LangSmith trace per
conversation. Raw audio never becomes span payload; callers may explicitly feed
the PCM into the wrapper to attach a bounded stereo conversation WAV.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

from langsmith._internal.voice.helpers import observe_safely
from langsmith._internal.voice.session import (
    DEFAULT_MAX_AUDIO_SECONDS,
    EventSession,
    add_metadata,
    start_session,
)
from langsmith.run_helpers import tracing_context

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langsmith import Client, RunTree
    from langsmith.run_trees import WriteReplica

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 24_000

# ``LatencyReport`` fields (seconds) -> turn metadata keys (milliseconds).
_TURN_LATENCY_FIELDS = {
    "stt_latency": "deepgram_stt_latency_ms",
    "ttt_token_latency": "deepgram_ttt_token_latency_ms",
    "ttt_text_latency": "deepgram_ttt_text_latency_ms",
    "ttt_tool_latency": "deepgram_ttt_tool_latency_ms",
    "ttt_thinking_latency": "deepgram_ttt_thinking_latency_ms",
    "tts_latency": "deepgram_tts_latency_ms",
    "total_latency": "deepgram_total_latency_ms",
}

# Housekeeping events that carry nothing worth a span.
_SILENT_EVENTS = frozenset(
    {"KeepAlive", "PromptUpdated", "SpeakUpdated", "SettingsApplied"}
)


def _json_message(frame: Any) -> dict[str, Any] | None:
    """Normalize a raw JSON text frame or typed Deepgram SDK message.

    Binary audio frames yield ``None``. The SDK's Pydantic messages are
    recognized structurally so Deepgram stays an optional dependency.
    """
    if isinstance(frame, dict):
        return frame
    if isinstance(frame, str):
        return json.loads(frame)
    if hasattr(frame, "model_dump"):
        return frame.model_dump(mode="json", exclude_none=True)
    return None


def _tool_arguments(value: Any) -> Any:
    """Decode Deepgram's JSON-encoded tool arguments when possible."""
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _latency_metadata(message: dict[str, Any]) -> dict[str, float]:
    """Convert the allowlisted ``LatencyReport`` fields to milliseconds."""
    return {
        key: round(message[field] * 1000, 3)
        for field, key in _TURN_LATENCY_FIELDS.items()
        if field in message
    }


class _DeepgramVoiceTracer:
    """Translate Deepgram wire messages into an ``EventSession`` trace."""

    def __init__(
        self,
        session: EventSession,
        *,
        is_agent_speaking: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._session = session
        self._is_agent_speaking = is_agent_speaking
        self._open_tools: dict[str, RunTree] = {}
        # The turn most recently closed by ``AgentAudioDone``; its
        # ``LatencyReport`` arrives afterwards.
        self._completed_turn: RunTree | None = None
        # After a barge-in, the talked-over response still sends its own
        # ``AgentAudioDone``, which must not close the new turn.
        self._interrupted_audio_pending = False

    def observe_sent(self, frame: Any) -> None:
        """Observe an outbound ``Settings`` or ``FunctionCallResponse``."""
        message = _json_message(frame)
        if message is None:
            return
        if message["type"] == "Settings":
            self._capture_settings(message)
        elif message["type"] == "FunctionCallResponse":
            self._close_tool(message)

    def observe(self, frame: Any) -> None:
        """Observe one inbound text or binary WebSocket frame."""
        message = _json_message(frame)
        if message is None:
            return
        message_type = message["type"]
        if message_type in _SILENT_EVENTS:
            return

        now = self._session.now()
        if message_type == "Welcome":
            add_metadata(self._session.run, deepgram_request_id=message["request_id"])
        elif message_type == "History":
            add_metadata(
                self._session.run,
                deepgram_history_message_count=len(message["history"]),
            )
        elif message_type == "UserStartedSpeaking":
            self._start_turn()
        elif message_type == "ConversationText":
            self._observe_conversation_text(message, now)
        elif message_type == "FunctionCallRequest":
            self._observe_tool_request(message)
        elif message_type == "FunctionCallResponse":
            self._close_tool(message)
        elif message_type == "FunctionCallCancelled":
            self._cancel_tools(message)
        elif message_type == "LatencyReport":
            latency = _latency_metadata(message)
            if self._session.has_open_turn:
                self._session.add_turn_metadata(**latency)
            elif self._completed_turn is not None:
                add_metadata(self._completed_turn, **latency)
                self._completed_turn.patch()
        elif message_type == "AgentAudioDone":
            self._record_event(message, now)
            if self._interrupted_audio_pending:
                self._interrupted_audio_pending = False
            else:
                self._completed_turn = self._session.end_turn()
        elif message_type in ("Error", "Warning"):
            with self._session.event_span(
                message, now, name=message_type, inbound=False
            ) as run:
                if message_type == "Error":
                    run.error = (
                        message.get("description") or "Deepgram Voice Agent error"
                    )
        else:
            self._record_event(message, now)

    def _start_turn(self) -> None:
        interrupted = (
            self._session.has_open_turn
            and self._is_agent_speaking is not None
            and self._is_agent_speaking()
        )
        if interrupted:
            self._session.add_turn_metadata(was_interrupted=True)
            self._interrupted_audio_pending = True
        self._session.start_turn()
        self._completed_turn = None

    def _observe_conversation_text(self, message: dict[str, Any], now: float) -> None:
        role = message["role"]
        content = message["content"].strip()
        if not content:
            return
        if role == "user":
            if not self._session.has_open_turn:
                self._start_turn()
            self._session.add_message(role, content)
            self._session.set_title(content)
            self._record_event(message, now, inputs={"role": role, "content": content})
        else:
            self._interrupted_audio_pending = False
            self._session.add_message(role, content)
            self._record_event(message, now, outputs={"role": role, "content": content})

    def _observe_tool_request(self, message: dict[str, Any]) -> None:
        calls = []
        for function in message["functions"]:
            call_id, name, arguments = (
                function["id"],
                function["name"],
                function["arguments"],
            )
            calls.append((call_id, name, arguments))
            self._open_tools[call_id] = self._session.open_span(
                name=name,
                run_type="tool",
                inputs={"args": _tool_arguments(arguments)},
                metadata={
                    "function_call_id": call_id,
                    "client_side": function["client_side"],
                },
            )
        self._session.add_tool_calls(calls)

    def _close_tool(self, message: dict[str, Any]) -> None:
        run = self._open_tools.pop(message["id"], None)
        if run is None:
            return
        self._session.add_tool_result(
            tool_call_id=message["id"],
            name=message["name"],
            content=message["content"],
        )
        self._session.close_span(run, outputs={"content": message["content"]})

    def _cancel_tools(self, message: dict[str, Any]) -> None:
        for function in message["functions"]:
            run = self._open_tools.pop(function["id"], None)
            if run is not None:
                run.error = "function call cancelled by Deepgram"
                self._session.close_span(run)

    def _capture_settings(self, message: dict[str, Any]) -> None:
        """Stamp the configured models, language, and audio format on the root."""
        agent = message.get("agent") or {}
        providers = {
            stage: (agent.get(stage) or {}).get("provider") or {}
            for stage in ("listen", "think", "speak")
        }
        metadata: dict[str, Any] = {
            "deepgram_listen_model": providers["listen"].get("model"),
            "deepgram_think_provider": providers["think"].get("type"),
            "deepgram_think_model": providers["think"].get("model"),
            "deepgram_speak_model": providers["speak"].get("model"),
            "deepgram_language": agent.get("language"),
        }
        for direction, config in (message.get("audio") or {}).items():
            for field in ("encoding", "sample_rate", "container"):
                metadata[f"deepgram_audio_{direction}_{field}"] = config.get(field)
        add_metadata(
            self._session.run,
            **{key: value for key, value in metadata.items() if value is not None},
        )

    def _record_event(
        self,
        message: dict[str, Any],
        now: float,
        *,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        with self._session.event_span(
            message,
            now,
            name=message["type"],
            inbound=inputs is not None,
            inputs=inputs,
            outputs=outputs,
        ):
            pass

    def finalize(self) -> None:
        """Error out any tool spans still open at teardown."""
        for run in self._open_tools.values():
            run.error = "function did not complete before the session ended"
            self._session.close_span(run)
        self._open_tools.clear()


class _TracedDeepgramVoiceConnection:
    """Transparent async WebSocket proxy with Deepgram-aware tracing hooks.

    Every attribute not defined here is delegated to the wrapped connection,
    so binary ``send_media`` and the like pass through untouched.
    """

    def __init__(
        self,
        connection: Any,
        tracer: _DeepgramVoiceTracer,
        session: EventSession,
    ) -> None:
        self._connection = connection
        self._tracer = tracer
        self._session = session
        self._aiter: Any = None

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_connection"), name)

    def __aiter__(self) -> _TracedDeepgramVoiceConnection:
        self._aiter = self._connection.__aiter__()
        return self

    async def __anext__(self) -> Any:
        frame = await self._aiter.__anext__()
        observe_safely(self._tracer.observe, frame)
        return frame

    async def recv(self, *args: Any, **kwargs: Any) -> Any:
        frame = await self._connection.recv(*args, **kwargs)
        observe_safely(self._tracer.observe, frame)
        return frame

    async def send(self, frame: Any, *args: Any, **kwargs: Any) -> Any:
        result = await self._connection.send(frame, *args, **kwargs)
        observe_safely(self._tracer.observe_sent, frame)
        return result

    async def send_settings(self, message: Any, *args: Any, **kwargs: Any) -> Any:
        """Send and observe typed Deepgram SDK settings."""
        result = await self._connection.send_settings(message, *args, **kwargs)
        observe_safely(self._tracer.observe_sent, message)
        return result

    async def send_function_call_response(
        self, message: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """Send and observe a typed Deepgram SDK tool response."""
        result = await self._connection.send_function_call_response(
            message, *args, **kwargs
        )
        observe_safely(self._tracer.observe_sent, message)
        return result

    def record_user_audio(self, pcm: bytes) -> None:
        """Record user PCM16 for the optional conversation WAV."""
        self._session.record_user(self._session.now(), pcm)

    def record_agent_audio(self, pcm: bytes) -> None:
        """Record played agent PCM16 for the optional conversation WAV."""
        self._session.record_agent(self._session.now(), pcm)


class _DeepgramVoiceTracingSession:
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
        self._tracer: _DeepgramVoiceTracer | None = None
        self._ctx: Any = None

    async def __aenter__(self) -> _TracedDeepgramVoiceConnection:
        self._session = start_session(
            thread_id=self._thread_id,
            sample_rate=self._sample_rate,
            project_name=self._project_name,
            tags=self._tags,
            metadata={**(self._metadata or {}), "ls_provider": "deepgram"},
            max_audio_seconds=self._max_audio_seconds,
            client=self._client,
            replicas=self._replicas,
            integration="deepgram-voice",
        )
        self._ctx = tracing_context(
            metadata={"thread_id": self._thread_id},
            tags=self._tags,
            project_name=self._project_name,
            replicas=self._replicas,
        )
        self._ctx.__enter__()
        self._tracer = _DeepgramVoiceTracer(
            self._session,
            is_agent_speaking=self._is_agent_speaking,
        )
        return _TracedDeepgramVoiceConnection(
            self._connection,
            self._tracer,
            self._session,
        )

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # Teardown is best-effort: closing the trace must neither mask the
        # caller's own exception nor raise a new one. The tracing context is
        # always restored (``finally``) so it can't leak past the session.
        try:
            if self._tracer is not None:
                self._tracer.finalize()
            if self._session is not None:
                if exc is not None:
                    self._session.run.error = f"{exc_type.__name__}: {exc}"
                self._session.finalize()
        except Exception:
            logger.warning(
                "Deepgram voice tracing: failed to finalize session",
                exc_info=True,
            )
        finally:
            if self._ctx is not None:
                self._ctx.__exit__(None, None, None)
        return False


def wrap_deepgram_voice(
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
) -> _DeepgramVoiceTracingSession:
    """Trace an async Deepgram Voice Agent connection.

    The returned async context manager yields a transparent connection proxy.
    Raw JSON or typed SDK server events are traced, binary agent-audio frames
    pass through untouched, and outbound ``FunctionCallResponse`` messages
    close their matching tool spans.
    """
    return _DeepgramVoiceTracingSession(
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
