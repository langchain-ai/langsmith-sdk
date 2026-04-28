"""Integration tests for Strands Agents OTEL exporter."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Sequence
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

pytest.importorskip("strands.telemetry", reason="strands-agents not installed")

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from strands import Agent, tool
from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from langsmith.integrations.strands_agents import LangSmithSpanExporter


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


class FakeStrandsModel(Model):
    """No-network BedrockModel replacement for string-model Agent tests."""

    instances: ClassVar[list["FakeStrandsModel"]] = []

    def __init__(self, model_id: str | None = None, **kwargs: Any) -> None:
        """Initialize the fake model with the requested model id."""
        self.config = {"model_id": model_id or "fake-strands-model"}
        self.instances.append(self)
        self.seen_messages: Messages | None = None
        self.seen_tool_specs: list[ToolSpec] | None = None
        self.seen_system_prompt: str | None = None

    def update_config(self, **model_config: Any) -> None:
        """Update fake model config."""
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        """Return fake model config."""
        return self.config

    async def structured_output(
        self,
        output_model: type[Any],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Return a minimal structured output response."""
        yield {"output": output_model()}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[dict[str, Any]] | None = None,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream one assistant response using Strands model event shapes."""
        self.seen_messages = messages
        self.seen_tool_specs = tool_specs
        self.seen_system_prompt = system_prompt

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": "Looks good."}}}
        yield {"contentBlockStop": {}}
        yield {
            "messageStop": {
                "stopReason": "end_turn",
                "additionalModelResponseFields": None,
            }
        }
        yield {
            "metadata": {
                "usage": {"inputTokens": 3, "outputTokens": 2, "totalTokens": 5},
                "metrics": {"latencyMs": 1},
            }
        }


@tool
def file_read(path: str) -> str:
    """Read a file from disk."""
    return f"contents of {path}"


@tool
def file_write(path: str, content: str) -> str:
    """Write content to a file."""
    return f"wrote {len(content)} chars to {path}"


@tool
def python_repl(code: str) -> str:
    """Execute Python code."""
    return f"executed {code}"


@tool
def shell(command: str) -> str:
    """Execute a shell command."""
    return f"ran {command}"


@tool
def journal(entry: str) -> str:
    """Record a journal entry."""
    return f"recorded {entry}"


def _install_strands_tracer(provider: TracerProvider):
    """Configure Strands tracer singleton to use a test tracer provider."""
    import strands.telemetry.tracer as strands_tracer

    previous = strands_tracer._tracer_instance
    tracer = strands_tracer.Tracer()
    tracer.tracer_provider = provider
    tracer.tracer = provider.get_tracer(tracer.service_name)
    strands_tracer._tracer_instance = tracer
    return previous


def test_exporter_transforms_real_strands_agent_spans():
    """Invoke a real Strands Agent and transform its emitted OTEL spans."""
    delegate = RecordingSpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(LangSmithSpanExporter(delegate=delegate))
    )

    import strands.telemetry.tracer as strands_tracer

    previous_tracer = _install_strands_tracer(provider)
    try:
        FakeStrandsModel.instances.clear()
        with patch("strands.agent.agent.BedrockModel", FakeStrandsModel):
            agent = Agent(
                tools=[file_read, file_write, python_repl, shell, journal],
                system_prompt=(
                    "You are an Expert Software Developer specializing in web "
                    "frameworks. Your task is to analyze project structures and "
                    "identify mappings."
                ),
                model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            )

            input = (
                "Do a short review of otel_strands_share.py. "
                "Focus on key functionality."
            )
            response = agent(input)

        provider.force_flush()
    finally:
        provider.shutdown()
        strands_tracer._tracer_instance = previous_tracer

    model = FakeStrandsModel.instances[0]
    assert str(response) == "Looks good.\n"
    assert model.seen_messages == [
        {
            "role": "user",
            "content": [
                {
                    "text": "Do a short review of otel_strands_share.py. "
                    "Focus on key functionality."
                }
            ],
        }
    ]
    assert model.seen_system_prompt == (
        "You are an Expert Software Developer specializing in web frameworks. "
        "Your task is to analyze project structures and identify mappings."
    )
    assert {spec["name"] for spec in model.seen_tool_specs or []} == {
        "file_read",
        "file_write",
        "python_repl",
        "shell",
        "journal",
    }

    spans_by_name = {span.name: span for span in delegate.spans}
    assert set(spans_by_name) == {
        "chat",
        "execute_event_loop_cycle",
        "invoke_agent Strands Agents",
    }

    agent_span = spans_by_name["invoke_agent Strands Agents"]
    assert agent_span.attributes["langsmith.span.kind"] == "chain"
    assert agent_span.attributes["gen_ai.agent.name"] == "Strands Agents"
    assert (
        agent_span.attributes["gen_ai.request.model"]
        == "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    assert agent_span.events == ()
    agent_prompt = json.loads(agent_span.attributes["gen_ai.prompt"])
    assert agent_prompt["messages"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Do a short review of otel_strands_share.py. "
                    "Focus on key functionality.",
                }
            ],
        }
    ]
    agent_completion = json.loads(agent_span.attributes["gen_ai.completion"])
    assert agent_completion == {
        "role": "assistant",
        "content": "Looks good.\n",
        "finish_reason": "end_turn",
    }

    cycle_span = spans_by_name["execute_event_loop_cycle"]
    assert cycle_span.attributes["langsmith.span.kind"] == "chain"
    assert cycle_span.events == ()

    llm_span = spans_by_name["chat"]
    assert llm_span.attributes["langsmith.span.kind"] == "llm"
    assert (
        llm_span.attributes["gen_ai.request.model"]
        == "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    assert llm_span.attributes["gen_ai.usage.input_tokens"] == 3
    assert llm_span.attributes["gen_ai.usage.output_tokens"] == 2
    assert llm_span.attributes["langsmith.metadata.ls_provider"] == "amazon_bedrock"
    assert llm_span.attributes["langsmith.metadata.ls_model_type"] == "chat"
    assert llm_span.events == ()

    prompt = json.loads(llm_span.attributes["gen_ai.prompt"])
    assert prompt["messages"] == [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are an Expert Software Developer specializing in web "
                    "frameworks. Your task is to analyze project structures and "
                    "identify mappings.",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Do a short review of otel_strands_share.py. "
                    "Focus on key functionality.",
                }
            ],
        },
    ]

    completion = json.loads(llm_span.attributes["gen_ai.completion"])
    assert completion == {
        "role": "assistant",
        "content": [{"type": "text", "text": "Looks good."}],
        "finish_reason": "end_turn",
    }
