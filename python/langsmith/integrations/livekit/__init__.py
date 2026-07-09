"""LangSmith integration for LiveKit Agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal.voice import set_thread_id

from .processor import LiveKitLangSmithSpanProcessor

logger = logging.getLogger(__name__)

__all__ = [
    "LiveKitLangSmithSpanProcessor",
    "configure_livekit",
    "set_thread_id",
]


@warn_beta
def configure_livekit(
    *,
    audio_path_provider: Optional[Callable[[], Optional[Path]]] = None,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    endpoint: Optional[str] = None,
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

    Args:
        audio_path_provider: zero-arg callable returning a local recording path
            whose bytes are embedded in the root span (console/dev only). For
            production, attach a LiveKit Egress recording via the returned
            processor's ``expect_recording`` / ``complete_recording`` methods.
        api_key / project / endpoint: LangSmith exporter config; default to the
            standard ``LANGSMITH_*`` resolution.

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
        audio_path_provider=audio_path_provider,
        api_key=api_key,
        project=project,
        endpoint=endpoint,
        **kwargs,
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    telemetry.set_tracer_provider(provider)  # LiveKit's hook (binds its tracer)
    otel_trace.set_tracer_provider(provider)  # OTel global (other instrumentation)
    return processor
