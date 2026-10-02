"""Client configuration for OpenTelemetry integration with LangSmith."""

import functools
import os
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
    except ImportError:
        TracerProvider = object  # type: ignore[assignment, misc]

from langsmith import utils as ls_utils


def _import_otel_client():
    """Dynamically import OTEL client modules when needed."""
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import]
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import (  # type: ignore[import]
            SERVICE_NAME,
            Resource,
        )
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import]
            BatchSpanProcessor,
        )

        return (
            OTLPSpanExporter,
            SERVICE_NAME,
            Resource,
            TracerProvider,
            BatchSpanProcessor,
        )
    except ImportError as e:
        warnings.warn(
            f"OTEL_ENABLED is set but OpenTelemetry packages are not installed: {e}"
        )
        return None


@functools.lru_cache(maxsize=1)
def _warn_legacy_traces_endpoint() -> None:
    warnings.warn(
        "LangSmith now treats OTEL_EXPORTER_OTLP_ENDPOINT as a base URL and "
        "appends /v1/traces. Your value ends in /traces, so it is being "
        "preserved unchanged for compatibility. This fallback will be "
        "removed in the v1 release of the SDK. Move this full URL to "
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT to use standard OpenTelemetry "
        "configuration.",
        UserWarning,
        stacklevel=3,
    )


def get_otlp_tracer_provider() -> "TracerProvider":
    """Get the OTLP tracer provider for LangSmith.

    This function creates a tracer provider that exports spans using the OTLP protocol
    with LangSmith-specific defaults:

    - OTEL_EXPORTER_OTLP_ENDPOINT: https://api.smith.langchain.com/otel
    - OTEL_EXPORTER_OTLP_HEADERS: Contains x-api-key from LangSmith API key and
      Langsmith-Project header if project is configured

    These defaults can be overridden by setting the environment variables before
    calling this function. OTEL_EXPORTER_OTLP_TRACES_ENDPOINT takes precedence as
    a full traces URL; OTEL_EXPORTER_OTLP_ENDPOINT is a base URL to which
    /v1/traces is appended unless it already ends in /traces for compatibility.
    Resolved values are passed to the exporter constructor
    rather than written to os.environ.

    Returns:
        TracerProvider: The OTLP tracer provider.
    """
    # Import OTEL modules dynamically
    otel_imports = _import_otel_client()
    if otel_imports is None:
        raise ImportError(
            "OpenTelemetry packages are required to use this function. "
            "Please install with `pip install langsmith[otel]`"
        )
    (
        OTLPSpanExporter,
        SERVICE_NAME,
        Resource,
        TracerProvider,
        BatchSpanProcessor,
    ) = otel_imports

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if not endpoint:
        base_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not base_endpoint:
            base_endpoint = f"{ls_utils.get_api_url(None)}/otel"
        if base_endpoint.endswith("/traces"):
            endpoint = base_endpoint
            _warn_legacy_traces_endpoint()
        else:
            endpoint = f"{base_endpoint.rstrip('/')}/v1/traces"

    # Configure headers with API key and project if available.
    # Build a dict because OTLPSpanExporter expects a mapping, not a string.
    headers_env = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS")
    if headers_env:
        headers = {
            k.strip(): v.strip()
            for k, v in (
                pair.split("=", 1) for pair in headers_env.split(",") if "=" in pair
            )
        }
    else:
        api_key = ls_utils.get_api_key(None) or ""
        headers = {"x-api-key": api_key}

        project = ls_utils.get_tracer_project()
        if project:
            headers["Langsmith-Project"] = project

    service_name = os.environ.get("OTEL_SERVICE_NAME", "langsmith")
    resource = Resource(
        attributes={
            SERVICE_NAME: service_name,
            # Marker to identify LangSmith's internal provider
            "langsmith.internal_provider": True,
        }
    )

    tracer_provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider
