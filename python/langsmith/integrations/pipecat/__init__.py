"""LangSmith integration for Pipecat."""

from __future__ import annotations

import logging
from typing import Any, Optional

from langsmith._internal._beta_decorator import warn_beta
from langsmith._internal.voice import set_thread_id, thread_id_from_context
from langsmith.integrations.pipecat.processor import PipecatLangSmithSpanProcessor

logger = logging.getLogger(__name__)

__all__ = [
    "PipecatLangSmithSpanProcessor",
    "configure_pipecat",
    "set_thread_id",
    "thread_id_from_context",
]


@warn_beta
def configure_pipecat(
    *,
    llm_span_kind: str = "llm",
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    endpoint: Optional[str] = None,
    service_name: str = "pipecat",
    **kwargs: Any,
) -> Optional[PipecatLangSmithSpanProcessor]:
    """Enable LangSmith tracing for a Pipecat pipeline.

    Installs Pipecat's OTel ``TracerProvider`` (via ``setup_tracing``) and
    registers a :class:`PipecatLangSmithSpanProcessor` that rewrites Pipecat's
    spans for LangSmith and exports them to LangSmith's OTLP endpoint. Enable
    tracing on the pipeline itself with
    ``PipelineTask(..., enable_tracing=True, enable_turn_tracking=True,
    params=PipelineParams(enable_metrics=True))``.

    To manage your own ``TracerProvider`` instead, skip this function and add
    ``PipecatLangSmithSpanProcessor(...)`` to your provider directly.

    To group a conversation's spans into a LangSmith thread, call
    :func:`set_thread_id` once per conversation (inside that conversation's
    asyncio task). The processor captures it as the conversation's spans start
    and applies it to every span in the trace — so it holds even for spans
    finished on a background task, and concurrent conversations stay separated.

    Args:
        llm_span_kind: LangSmith run kind for Pipecat's ``llm`` span; see the
            :mod:`~langsmith.integrations.pipecat.processor` module docstring.
        api_key / project / endpoint: LangSmith exporter config; default to the
            standard ``LANGSMITH_*`` resolution.
        service_name: OTel service name for the provider.

    Returns:
        The registered processor (so callers can e.g. ``attach_audio_buffer``),
        or ``None`` if Pipecat / OpenTelemetry aren't installed.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from pipecat.utils.tracing import setup  # type: ignore[import-not-found]
    except ImportError as e:
        logger.warning("Missing dependency for Pipecat tracing: %s", e)
        return None

    # ``exporter=None`` creates/installs the TracerProvider without an export
    # pipeline; our processor wraps the LangSmith exporter itself.
    setup.setup_tracing(service_name=service_name, exporter=None, console_export=False)

    processor = PipecatLangSmithSpanProcessor(
        llm_span_kind=llm_span_kind,
        api_key=api_key,
        project=project,
        endpoint=endpoint,
        **kwargs,
    )
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(processor)
    else:
        logger.warning(
            "Active OTel TracerProvider is not an SDK TracerProvider; "
            "PipecatLangSmithSpanProcessor was not registered."
        )
    return processor
