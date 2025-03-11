"""Client configuration for OpenTelemetry integration with LangSmith."""
import os
from langsmith import utils as ls_utils

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME

def get_otlp_tracer_provider() -> TracerProvider:
    """Get the OTLP tracer provider for LangSmith.
    
    This function creates a tracer provider that exports spans using the OTLP protocol
    with LangSmith-specific defaults:
    
    - OTEL_EXPORTER_OTLP_ENDPOINT: https://api.smith.langchain.com/otel
    - OTEL_EXPORTER_OTLP_HEADERS: Contains x-api-key from LangSmith API key and
      Langsmith-Project header if project is configured
    
    These defaults can be overridden by setting the environment variables before
    calling this function.
    
    Returns:
        TracerProvider: The OTLP tracer provider.
    """
    # Set LangSmith-specific defaults if not already set in environment
    if "OTEL_EXPORTER_OTLP_ENDPOINT" not in os.environ:
        ls_endpoint = ls_utils.get_api_url(None)
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{ls_endpoint}/otel"
    
    # Configure headers with API key and project if available
    if "OTEL_EXPORTER_OTLP_HEADERS" not in os.environ:
        api_key = ls_utils.get_api_key(None)
        headers = f"x-api-key={api_key}"
        
        project = ls_utils.get_tracer_project()
        if project:
            headers += f",Langsmith-Project={project}"
        
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = headers
    
    service_name = os.environ.get("OTEL_SERVICE_NAME", "langsmith")
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    tracer_provider = TracerProvider(resource=resource)
    
    otlp_exporter = OTLPSpanExporter()
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider
