"""Integration tests for Strands Agents OTEL exporter."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

import pytest

pytest.importorskip("strands.telemetry", reason="strands-agents not installed")
pytest.importorskip("strands_tools", reason="strands-agents-tools not installed")

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from strands import Agent
from strands_tools import file_read, file_write, journal, python_repl, shell

from langsmith.integrations.otel.processor import OtelExporter
from langsmith.integrations.strands_agents import LangSmithSpanExporter

MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
INPUT = "Do a short review of otel_strands_share.py. Focus on key functionality."
SYSTEM_PROMPT = (
    "You are an Expert Software Developer specializing in web frameworks. "
    "Your task is to analyze project structures and identify mappings."
)


class RecordingSpanExporter(SpanExporter):
    """Exporter that records spans exported by the OTEL SDK."""

    def __init__(self) -> None:
        """Initialize the recording exporter."""
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Record exported spans."""
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """No-op shutdown."""
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """No-op flush."""
        return True


class TeeSpanExporter(SpanExporter):
    """Exporter that forwards spans to multiple exporters."""

    def __init__(self, *exporters: SpanExporter) -> None:
        """Initialize with delegate exporters."""
        self.exporters = exporters

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to all delegates."""
        results = [exporter.export(spans) for exporter in self.exporters]
        if all(result == SpanExportResult.SUCCESS for result in results):
            return SpanExportResult.SUCCESS
        return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shut down all delegates."""
        for exporter in self.exporters:
            exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush all delegates."""
        return all(exporter.force_flush(timeout_millis) for exporter in self.exporters)


def _install_strands_tracer(provider: TracerProvider) -> Any:
    """Configure Strands tracer singleton to use a test tracer provider."""
    import strands.telemetry.tracer as strands_tracer

    previous = strands_tracer._tracer_instance
    tracer = strands_tracer.Tracer()
    tracer.tracer_provider = provider
    tracer.tracer = provider.get_tracer(tracer.service_name)
    strands_tracer._tracer_instance = tracer
    return previous


def _span_has_prompt_text(span: ReadableSpan, text: str) -> bool:
    prompt = span.attributes.get("gen_ai.prompt")
    if not isinstance(prompt, str):
        return False
    return text in prompt


def _span_has_completion(span: ReadableSpan) -> bool:
    return isinstance(span.attributes.get("gen_ai.completion"), str)


@pytest.mark.skipif(
    not (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_PROFILE")
        or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
    ),
    reason="Live Strands/Bedrock integration test requires AWS credentials.",
)
@pytest.mark.skipif(
    not os.getenv("LANGSMITH_API_KEY"),
    reason="Live Strands/LangSmith integration test requires LANGSMITH_API_KEY.",
)
def test_exporter_transforms_live_strands_agent_spans(tmp_path, monkeypatch):
    """Invoke a real Strands Agent and transform its emitted OTEL spans."""
    (tmp_path / "otel_strands_share.py").write_text(
        "def setup_langsmith_telemetry():\n"
        "    return 'sets up Strands OTEL tracing for LangSmith'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    recorder = RecordingSpanExporter()
    langsmith_exporter = OtelExporter()
    delegate = TeeSpanExporter(recorder, langsmith_exporter)
    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(LangSmithSpanExporter(delegate=delegate))
    )

    import strands.telemetry.tracer as strands_tracer

    previous_tracer = _install_strands_tracer(provider)
    try:
        agent = Agent(
            tools=[file_read, file_write, python_repl, shell, journal],
            system_prompt=SYSTEM_PROMPT,
            model=MODEL_ID,
        )

        input = INPUT
        response = agent(input)

        provider.force_flush()
    finally:
        provider.shutdown()
        strands_tracer._tracer_instance = previous_tracer

    assert response is not None
    spans_by_name = {span.name: span for span in recorder.spans}

    agent_spans = [
        span for span in recorder.spans if span.name.startswith("invoke_agent")
    ]
    assert agent_spans, [span.name for span in recorder.spans]
    agent_span = agent_spans[0]
    assert agent_span.attributes["langsmith.span.kind"] == "chain"
    assert agent_span.attributes["gen_ai.agent.name"] == "Strands Agents"
    assert agent_span.attributes["gen_ai.request.model"] == MODEL_ID
    assert _span_has_prompt_text(agent_span, INPUT)
    assert _span_has_completion(agent_span)

    assert "execute_event_loop_cycle" in spans_by_name
    cycle_span = spans_by_name["execute_event_loop_cycle"]
    assert cycle_span.attributes["langsmith.span.kind"] == "chain"
    assert _span_has_prompt_text(cycle_span, INPUT)

    llm_spans = [span for span in recorder.spans if span.name == "chat"]
    assert llm_spans, [span.name for span in recorder.spans]
    assert any(_span_has_prompt_text(span, INPUT) for span in llm_spans)
    assert any(_span_has_completion(span) for span in llm_spans)

    for llm_span in llm_spans:
        assert llm_span.attributes["langsmith.span.kind"] == "llm"
        assert llm_span.attributes["gen_ai.request.model"] == MODEL_ID
        assert llm_span.attributes["langsmith.metadata.ls_provider"] == "amazon_bedrock"
        assert llm_span.attributes["langsmith.metadata.ls_model_type"] == "chat"
        assert not any(event.name.startswith("gen_ai.") for event in llm_span.events)

    prompt_span = next(span for span in llm_spans if _span_has_prompt_text(span, INPUT))
    prompt = json.loads(prompt_span.attributes["gen_ai.prompt"])
    roles = [message["role"] for message in prompt["messages"]]
    assert "user" in roles
    assert "system" in roles
