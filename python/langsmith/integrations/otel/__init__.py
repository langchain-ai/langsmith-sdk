"""OpenTelemetry integration for LangSmith."""

import logging
import os
from typing import Optional, cast

logger = logging.getLogger(__name__)

__all__ = ["initialize_otel"]


def initialize_otel(
    api_key: Optional[str] = None,
    project_name: Optional[str] = None,
    SpanProcessor: Optional[type] = None,
) -> bool:
    """Initialize the Otel span processor for LangSmith."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.trace import NoOpTracer, ProxyTracer, ProxyTracerProvider

        existing_provider = cast(TracerProvider, trace.get_tracer_provider())
        tracer = existing_provider.get_tracer(__name__)

        # check if otel is already initialized
        if (
            isinstance(existing_provider, ProxyTracerProvider)
            and hasattr(tracer, "_tracer")
            and isinstance(
                cast(
                    ProxyTracer,  # type: ignore[attr-defined, name-defined]
                    tracer,
                )._tracer,
                NoOpTracer,
            )
        ):
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
        else:
            logger.warning(
                "Otel is already initialized, skipping LangSmith initialization"
            )

        api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        if not api_key:
            return False

        from .processor import OtelSpanProcessor

        project_name = project_name or os.environ.get("LANGSMITH_PROJECT")

        processor = OtelSpanProcessor(
            api_key=api_key, project=project_name, SpanProcessor=SpanProcessor
        )
        provider.add_span_processor(processor)  # type: ignore
        return True
    except Exception as e:
        logger.warning("Failed to initialize Otel for LangSmith:", e)
        return False
