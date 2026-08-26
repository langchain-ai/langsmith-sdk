"""LangSmith integration for LiveKit Agents."""

from __future__ import annotations

import logging
from typing import Any, Optional

from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal.voice import set_thread_id

from .processor import (
    DEFAULT_RECORDING_TIMEOUT_SECONDS,
    LiveKitLangSmithSpanProcessor,
)

logger = logging.getLogger(__name__)

__all__ = [
    "LiveKitLangSmithSpanProcessor",
    "configure_livekit",
    "set_thread_id",
]


@warn_beta
def configure_livekit(
    *,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    endpoint: Optional[str] = None,
    await_recording: bool = True,
    recording_timeout_seconds: float = DEFAULT_RECORDING_TIMEOUT_SECONDS,
    **kwargs: Any,
) -> Optional[LiveKitLangSmithSpanProcessor]:
    """Enable LangSmith tracing for a LiveKit Agents worker.

    Builds a ``TracerProvider`` with a :class:`LiveKitLangSmithSpanProcessor`
    (which rewrites LiveKit's ``lk.*`` spans for LangSmith and exports them to
    LangSmith's OTLP endpoint) and registers it as both LiveKit's tracer provider
    and the OTel global. Call before starting the worker.

    To manage your own ``TracerProvider`` instead, skip this function: construct
    :class:`LiveKitLangSmithSpanProcessor` directly, add it to your provider, and
    register that provider with LiveKit via
    ``livekit.agents.telemetry.set_tracer_provider(...)`` — LiveKit only emits
    spans through the provider its tracer is bound to.

    To group a conversation's spans into a LangSmith thread, call
    :func:`set_thread_id` once per conversation (inside that conversation's
    asyncio task). The processor captures it as the conversation's spans start
    and applies it to every span in the trace — so it holds even for spans
    finished on a background task, and concurrent conversations stay separated.

    For a realtime (speech-to-speech) model, also call
    :meth:`LiveKitLangSmithSpanProcessor.instrument_session` on the returned
    processor: the user transcript arrives as a session event rather than on a
    span, so without it the trace shows only the agent's turns.

    Each conversation's root span is held open until its recording arrives, so
    the recording can be attached and its time origin stamped on the trace.
    Deliver it from an ``on_session_end`` callback::

        processor = configure_livekit()


        async def on_session_end(ctx: JobContext) -> None:
            processor.attach_session_report(
                ctx.make_session_report(), thread_id=ctx.room.name
            )


        server = AgentServer()


        @server.rtc_session(on_session_end=on_session_end)
        async def entrypoint(ctx: JobContext) -> None: ...

    With LiveKit Egress (or your own capture), call
    :meth:`LiveKitLangSmithSpanProcessor.complete_recording` with the bytes and
    the recording's ``started_at`` instead.

    Args:
        api_key / project / endpoint: LangSmith exporter config; default to the
            standard ``LANGSMITH_*`` resolution.
        await_recording: hold each root span until a recording is delivered.
            Pass ``False`` when tracing a session with no audio.
        recording_timeout_seconds: how long that hold lasts before the trace is
            exported without audio.

    Returns:
        The processor, or ``None`` if LiveKit / OpenTelemetry aren't installed.
    """
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider

        from livekit.agents import telemetry  # type: ignore[import-not-found]
    except ImportError as e:
        logger.warning("Missing dependency for LiveKit tracing: %s", e)
        return None

    processor = LiveKitLangSmithSpanProcessor(
        api_key=api_key,
        project=project,
        endpoint=endpoint,
        await_recording=await_recording,
        recording_timeout_seconds=recording_timeout_seconds,
        **kwargs,
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    telemetry.set_tracer_provider(provider)  # LiveKit's hook (binds its tracer)
    otel_trace.set_tracer_provider(provider)  # OTel global (other instrumentation)
    return processor
