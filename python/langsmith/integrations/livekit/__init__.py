"""LangSmith integration for LiveKit Agents."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal.voice import set_thread_id

from .processor import (
    DEFAULT_RECORDING_TIMEOUT_SECONDS,
    LiveKitLangSmithSpanProcessor,
    RecordingMode,
)

logger = logging.getLogger(__name__)

__all__ = [
    "LiveKitLangSmithSpanProcessor",
    "RecordingMode",
    "configure_livekit",
    "set_thread_id",
]


@warn_beta
def configure_livekit(
    *,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    endpoint: Optional[str] = None,
    audio_path_provider: Optional[Callable[[], Optional[Path]]] = None,
    recording_mode: RecordingMode = "session_report",
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

    Each conversation's root span is held until its session report arrives. The
    processor registers an additive ``AgentSession`` close listener and captures
    that report automatically; no ``on_session_end`` callback is required. In
    ``session_report`` mode the report's recording is attached with its chat
    history.

    With LiveKit Egress (or your own capture), configure
    ``recording_mode="egress"`` and deliver each conversation's audio when it is
    available::

        processor.complete_recording(
            thread_id,
            audio_bytes,
            started_at=egress_started_at,
        )

    Existing code may instead call ``processor.expect_recording(thread_id)`` at
    conversation start. That marks only that conversation as egress, even when
    the processor's default mode is ``session_report`` or ``none``. It may be
    called before the conversation's spans start. The automatic report and
    recording may arrive in either order; an egress root is released after both,
    or after ``recording_timeout_seconds`` as failure protection. Use
    ``recording_mode="none"`` to attach report data without audio.

    Args:
        api_key / project / endpoint: LangSmith exporter config; default to the
            standard ``LANGSMITH_*`` resolution.
        audio_path_provider: Deprecated compatibility parameter. It is ignored.
        recording_mode: ``"session_report"``, ``"egress"``, or ``"none"``.
        recording_timeout_seconds: how long the root waits for required session
            data before it is exported with whatever is available.

    Returns:
        The processor, or ``None`` if LiveKit / OpenTelemetry aren't installed.
    """
    if audio_path_provider is not None:
        warnings.warn(
            "audio_path_provider is deprecated and ignored.",
            DeprecationWarning,
            stacklevel=2,
        )

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
        recording_mode=recording_mode,
        recording_timeout_seconds=recording_timeout_seconds,
        **kwargs,
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    telemetry.set_tracer_provider(provider)  # LiveKit's hook (binds its tracer)
    otel_trace.set_tracer_provider(provider)  # OTel global (other instrumentation)
    return processor
