"""LangSmith integration for LiveKit Agents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from .._voice import warn_in_development
from .processor import LiveKitLangSmithSpanProcessor

logger = logging.getLogger(__name__)

warn_in_development("livekit")

__all__ = ["LiveKitLangSmithSpanProcessor", "configure_livekit"]


def configure_livekit(
    *,
    thread_id_provider: Optional[Callable[[], Optional[str]]] = None,
    audio_path_provider: Optional[Callable[[], Optional[Path]]] = None,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    endpoint: Optional[str] = None,
    set_global_provider: bool = True,
    **kwargs: Any,
) -> Optional[LiveKitLangSmithSpanProcessor]:
    """Enable LangSmith tracing for a LiveKit Agents worker.

    Builds a ``TracerProvider`` with a :class:`LiveKitLangSmithSpanProcessor`
    (which rewrites LiveKit's ``lk.*`` spans for LangSmith and exports them to
    LangSmith's OTLP endpoint) and registers it as both LiveKit's tracer provider
    and the OTel global. Call before starting the worker.

    To manage your own ``TracerProvider`` instead, pass
    ``set_global_provider=False`` and add the returned processor to your provider.

    Args:
        thread_id_provider: opt-in conversation id for LangSmith thread grouping.
        audio_path_provider: zero-arg callable returning a local recording path
            whose bytes are embedded in the root span (console/dev only). For
            production, attach a LiveKit Egress recording via the returned
            processor's ``expect_recording`` / ``complete_recording`` methods.
        api_key / project / endpoint: LangSmith exporter config; default to the
            standard ``LANGSMITH_*`` resolution.
        set_global_provider: when ``True`` (default), create and register the
            tracer provider for you.

    Returns:
        The processor, or ``None`` if LiveKit / OpenTelemetry aren't installed.
    """
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError as e:
        logger.warning("Missing dependency for LiveKit tracing: %s", e)
        return None

    processor = LiveKitLangSmithSpanProcessor(
        thread_id_provider=thread_id_provider,
        audio_path_provider=audio_path_provider,
        api_key=api_key,
        project=project,
        endpoint=endpoint,
        **kwargs,
    )

    if set_global_provider:
        try:
            from livekit.agents.telemetry import set_tracer_provider
        except ImportError as e:
            logger.warning("Missing dependency for LiveKit tracing: %s", e)
            return None
        provider = TracerProvider()
        provider.add_span_processor(processor)
        set_tracer_provider(provider)  # LiveKit's hook
        otel_trace.set_tracer_provider(provider)  # OTel global
    return processor
