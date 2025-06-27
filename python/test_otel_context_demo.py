#!/usr/bin/env python3
"""Demo script to show OpenTelemetry context propagation with LangSmith tracing.

This script demonstrates that OpenTelemetry spans created within @traceable functions
now properly inherit the LangSmith trace context, creating correct parent-child
relationships in the trace hierarchy.
"""

import os
import time

# Set environment variables for LangSmith and OpenTelemetry
os.environ["LANGSMITH_OTEL_ENABLED"] = "true"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"

# Clear the cache to ensure environment variables are read
from langsmith import utils

utils.get_env_var.cache_clear()

# Set up OpenTelemetry console exporter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

# Initialize OpenTelemetry
tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
console_exporter = ConsoleSpanExporter()
# Use SimpleSpanProcessor instead of BatchSpanProcessor for immediate output
span_processor = SimpleSpanProcessor(console_exporter)
tracer_provider.add_span_processor(span_processor)

# Get a tracer
tracer = trace.get_tracer(__name__)

# Import LangSmith traceable decorator
from langsmith import traceable


@traceable
def get_greeting(name: str = "World") -> str:
    """Get a greeting message - this is a LangSmith traced function."""
    # This OpenTelemetry span should now inherit from the LangSmith trace context
    with tracer.start_as_current_span("OTel get_greeting") as span:
        span.set_attribute("greeting.name", name)
        span.add_event("Creating greeting message")

        greeting = f"Hello there {name}! 😊"
        span.set_attribute("greeting.message", greeting)

        # Simulate some work
        time.sleep(0.1)

        return greeting


@traceable
def process_request(user_name: str) -> dict:
    """Process a user request - another LangSmith traced function."""
    with tracer.start_as_current_span("OTel process_request") as span:
        span.set_attribute("user.name", user_name)
        span.add_event("Processing user request")

        # Call the greeting function (this should create a child span)
        greeting = get_greeting(user_name)

        response = {"greeting": greeting, "timestamp": time.time(), "user": user_name}

        span.set_attribute("response.greeting", greeting)
        span.add_event("Request processed successfully")

        return response


@traceable
def langsmith_nested_function(data: str) -> str:
    """A LangSmith function that gets called within an existing OTel trace."""
    return f"Processed: {data}"


def test_langchain_integration():
    """Test OpenTelemetry context propagation with LangChain."""
    try:
        from langchain_core.prompts import PromptTemplate
        from langchain_core.runnables import RunnableLambda

        print("\n📋 Test 3: LangChain integration with OTel context propagation...")

        # Create a simple LangChain chain
        def format_response(prompt_value) -> str:
            """Format a response with OpenTelemetry span."""
            with tracer.start_as_current_span("langchain_format_response") as span:
                prompt_text = str(prompt_value)
                span.set_attribute("input.prompt", prompt_text)
                response = f"Hello from LangChain! Prompt was: {prompt_text}"
                span.set_attribute("output.response", response)
                return response

        prompt = PromptTemplate.from_template("Process: {name}")
        formatter = RunnableLambda(format_response)
        chain = prompt | formatter

        # Test 3a: LangChain within existing OTel trace
        with tracer.start_as_current_span("langchain_test") as span:
            span.set_attribute("test.type", "langchain_integration")
            result3a = chain.invoke({"name": "Bob"})
            span.set_attribute("test.result", result3a)

        print(f"✅ LangChain Result: {result3a}")

        # Test 3b: OTel span within LangChain traced operation
        def traced_langchain_operation(prompt_value) -> str:
            with tracer.start_as_current_span("nested_otel_in_langchain") as span:
                span.set_attribute("nested.operation", "within_langchain")
                return f"Nested OTel processing: {str(prompt_value)}"

        nested_chain = prompt | RunnableLambda(traced_langchain_operation)
        result3b = nested_chain.invoke({"name": "Charlie"})
        print(f"✅ Nested OTel in LangChain Result: {result3b}")

        return True

    except ImportError:
        print("\n⚠️  LangChain not available, skipping LangChain integration test...")
        return False


def main():
    """Main function to demonstrate the trace context propagation."""
    print("🚀 Starting OpenTelemetry context propagation demo...")
    print("=" * 60)

    # Test 1: LangSmith trace with OTel spans inside
    print("\n📋 Test 1: LangSmith @traceable functions with OTel spans inside...")
    result1 = process_request("Alice")
    print(f"✅ Result 1: {result1}")

    # Test 2: OTel trace with LangSmith spans inside
    print("\n📋 Test 2: OTel trace with LangSmith @traceable functions inside...")
    with tracer.start_as_current_span("big_otel_operation") as span:
        span.set_attribute("operation.type", "demo")
        span.add_event("Starting nested LangSmith operation")

        # This should inherit from the existing OTel trace
        result2 = langsmith_nested_function("test_data")

        span.set_attribute("nested.result", result2)
        span.add_event("Completed nested LangSmith operation")

    print(f"✅ Result 2: {result2}")

    # Test 3: LangChain integration
    langchain_available = test_langchain_integration()

    # Force flush to ensure all spans are exported
    print("\n📤 Flushing spans to console...")
    tracer_provider.force_flush(timeout_millis=5000)

    print("\n🎯 Demo complete!")
    print("\nLook for the console output above to see:")
    print("1. Test 1: LangSmith spans with OTel spans properly nested")
    print("2. Test 2: OTel spans with LangSmith spans properly nested")
    if langchain_available:
        print("3. Test 3: LangChain integration with OTel context propagation")
    print("4. Trace IDs show proper inheritance in all directions")
    print("5. Parent-child relationships are correctly established")


if __name__ == "__main__":
    main()
