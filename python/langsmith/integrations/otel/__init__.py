"""OpenTelemetry integration for LangSmith."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from langsmith import utils as ls_utils
from langsmith.client import Client

from ._utils import otel_safe_attribute_value, set_langsmith_metadata_attribute

if TYPE_CHECKING:
    from opentelemetry.trace import Span, SpanContext

    from .processor import OtelExporter, OtelSpanProcessor

logger = logging.getLogger(__name__)

__all__ = [
    "configure",
    "OtelSpanProcessor",
    "OtelExporter",
    "langsmith_run_id_from_otel_span_id",
    "get_langsmith_run_url_for_span",
    "otel_safe_attribute_value",
    "set_langsmith_metadata_attribute",
]


def __getattr__(name: str) -> Any:
    """Lazily import processor exports so offline helpers stay dependency-free."""
    if name in ("OtelSpanProcessor", "OtelExporter"):
        from . import processor

        return getattr(processor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def langsmith_run_id_from_otel_span_id(span_id: Union[int, bytes]) -> uuid.UUID:
    """Map an OpenTelemetry span ID to its LangSmith run ID.

    The LangSmith backend derives a run's UUID from the OTel span ID during
    ingest: the span-ID bytes are copied right-aligned into a 16-byte,
    zero-padded buffer, and those bytes become the run UUID.

    This mapping is deterministic and fully offline: it makes no network
    request and does not require `opentelemetry` to be installed. The span ID
    to run ID relationship is fixed by the server's ingest rule, so the run ID
    is stable regardless of when (or whether) ingest has completed.

    Args:
        span_id: The OTel span ID, either as an `int` (as returned by
            `span.get_span_context().span_id`) or as raw `bytes` (8 to 16
            bytes; left-padded with zeros to 16 bytes).

    Returns:
        The LangSmith run ID as a `uuid.UUID`.
    """
    if isinstance(span_id, bytes):
        if not 1 <= len(span_id) <= 16:
            raise ValueError(f"span_id bytes must be 1-16 bytes, got {len(span_id)}")
        raw = span_id.rjust(16, b"\x00")
    elif isinstance(span_id, bool):
        # bool is an int subclass; reject to avoid silent True/False span IDs.
        raise TypeError("span_id must be int or bytes, got bool")
    elif isinstance(span_id, int):
        # OTel span IDs are non-zero 64-bit integers; 0 is the invalid sentinel.
        if not 1 <= span_id < (1 << 64):
            raise ValueError("span_id int must be a non-zero 64-bit value")
        raw = span_id.to_bytes(16, "big")
    else:
        raise TypeError(f"span_id must be int or bytes, got {type(span_id)}")
    if raw == b"\x00" * 16:
        raise ValueError("span_id is all-zero, which is not a valid OTel span ID")
    return uuid.UUID(bytes=raw)


def _extract_span_id(span: Union[Span, SpanContext]) -> int:
    """Extract the integer span ID from an OTel span or span context."""
    from opentelemetry.trace import Span

    ctx = span.get_span_context() if isinstance(span, Span) else span
    return ctx.span_id


def get_langsmith_run_url_for_span(
    span: Union[Span, SpanContext],
    project_id: uuid.UUID,
    *,
    client: Optional[Client] = None,
) -> str:
    """Build the LangSmith run URL for a native OpenTelemetry span.

    Useful when your application creates and exports OTel spans to LangSmith
    and wants to surface a run URL immediately, without polling or waiting for
    asynchronous OTel ingest to complete.

    The span ID to run ID mapping is deterministic and offline (see
    `langsmith_run_id_from_otel_span_id`). The returned URL is "eventually
    valid": it points at the run that will materialize once OTel ingest
    finishes, which may not have happened yet at the time of the call.

    Network usage:
        - The span to run ID mapping is fully offline.
        - Resolving `tenant_id` and `host_url` for the URL uses `client`
          (a default `Client` is constructed if none is given).

    Args:
        span: An OTel span or span context.
        project_id: The LangSmith project (session) ID.
        client: Optional `Client` used to resolve tenant and host URL.

    Returns:
        The full LangSmith run URL.
    """
    client = client or Client()
    run_id = langsmith_run_id_from_otel_span_id(_extract_span_id(span))
    return (
        f"{client._host_url}/o/{client._get_tenant_id()}/projects/p/{project_id}/"
        f"r/{run_id}?poll=true"
    )


def configure(
    api_key: Optional[str] = None,
    project_name: Optional[str] = None,
    SpanProcessor: Optional[type] = None,
) -> bool:
    """Configure OpenTelemetry with LangSmith as the `TracerProvider`.

    Initializes OpenTelemetry with LangSmith as the primary and only `TracerProvider`.

    Usage:
        >>> from langsmith.integrations.otel import configure
        >>> configure(  # doctest: +SKIP
        ...     api_key="your-api-key", project_name="your-project"
        ... )

        Using environment variables:
        >>> # Set LANGSMITH_API_KEY and LANGSMITH_PROJECT
        >>> configure()  # Will use env vars  # doctest: +SKIP

    !!! warning

        This function is only for when LangSmith is your ONLY OpenTelemetry source.

        It sets the global TracerProvider, which can only be done once per application.

    This function will fail if OpenTelemetry is already initialized with another
    `TracerProvider` (you cannot override an existing `TracerProvider`).

    If you already have OpenTelemetry set up with other tools, use `OtelSpanProcessor`
    directly to add LangSmith to your existing setup:

    !!! example "Adding LangSmith to existing OTEL setup"
        ```python
        from opentelemetry import trace
        from langsmith.integrations.otel.processor import OtelSpanProcessor

        # Use your existing provider (already initialized)
        provider = trace.get_tracer_provider()

        # Add LangSmith processor to existing provider
        langsmith_processor = OtelSpanProcessor(
            api_key="your-api-key", project="your-project"
        )
        provider.add_span_processor(langsmith_processor)
        ```

    Args:
        api_key: LangSmith API key. Defaults to `LANGSMITH_API_KEY` env var.
        project_name: Project name. Defaults to `LANGSMITH_PROJECT` env var.
        SpanProcessor: Span processor class to use. Defaults to `BatchSpanProcessor`.

    Returns:
        `True` if configuration succeeded, `False` if `TracerProvider` already exists.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.trace import NoOpTracer, ProxyTracer, ProxyTracerProvider

        existing_provider = cast(TracerProvider, trace.get_tracer_provider())
        tracer = existing_provider.get_tracer(__name__)

        # Check if OpenTelemetry is in its default uninitialized state
        # (ProxyTracerProvider with NoOpTracer means no real TracerProvider was set)
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
            # Safe to set TracerProvider since none exists yet
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
        else:
            logger.warning(
                "OpenTelemetry TracerProvider is already set. "
                "Cannot override existing TracerProvider. Use OtelSpanProcessor "
                "directly to add LangSmith to your existing provider instead."
            )
            return False

        api_key = api_key or ls_utils.get_api_key(None)
        if not api_key:
            return False

        project_name = project_name or ls_utils.get_tracer_project()

        from .processor import OtelSpanProcessor

        processor = OtelSpanProcessor(
            api_key=api_key, project=project_name, SpanProcessor=SpanProcessor
        )
        provider.add_span_processor(processor)  # type: ignore
        return True
    except Exception as e:
        logger.warning("Failed to initialize Otel for LangSmith:", e)
        return False
