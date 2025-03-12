import logging
from typing import Any, Dict, Literal

try:
    from agents import tracing  # type: ignore[import]

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

logger = logging.getLogger(__name__)

RunTypeT = Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]

if HAVE_AGENTS:

    def get_run_type(span: tracing.Span) -> RunTypeT:
        span_type = getattr(span.span_data, "type", None)
        if span_type in ["agent", "handoff", "custom"]:
            return "chain"
        elif span_type in ["function", "guardrail"]:
            return "tool"
        elif span_type in ["generation", "response"]:
            return "llm"
        else:
            return "chain"

    def get_run_name(span: tracing.Span) -> str:
        if hasattr(span.span_data, "name") and span.span_data.name:
            return span.span_data.name
        span_type = getattr(span.span_data, "type", None)
        if span_type == "generation":
            return "Generation"
        elif span_type == "response":
            return "Response"
        elif span_type == "handoff":
            return "Handoff"
        else:
            return "Span"

    def _extract_function_span_data(
        span_data: tracing.FunctionSpanData,
    ) -> Dict[str, Any]:
        return {"inputs": span_data.input, "outputs": span_data.output}

    def _extract_generation_span_data(
        span_data: tracing.GenerationSpanData,
    ) -> Dict[str, Any]:
        data = {
            "inputs": span_data.input,
            "outputs": span_data.output,
            "metadata": {
                "model": span_data.model,
                "model_config": span_data.model_config,
            },
        }
        if span_data.usage:
            data["usage_metadata"] = {
                "total_tokens": span_data.usage.get("total_tokens"),
                "input_tokens": span_data.usage.get("prompt_tokens"),
                "output_tokens": span_data.usage.get("completion_tokens"),
            }
        return data

    def _extract_response_span_data(
        span_data: tracing.ResponseSpanData,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if span_data.input is not None:
            data["inputs"] = {"messages": list(span_data.input)}
        if span_data.response is not None:
            data["outputs"] = {
                "messages": [
                    output.model_dump() for output in span_data.response.output
                ]
            }
            data["metadata"] = span_data.response.metadata or {}
            data["metadata"].update(
                span_data.response.model_dump(
                    exclude={"input", "output", "metadata", "usage"}
                )
            )
            if span_data.response.usage:
                usage = span_data.response.usage
                data["usage_metadata"] = {
                    "total_tokens": usage.total_tokens,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                }
        return data

    def _extract_agent_span_data(span_data: tracing.AgentSpanData) -> Dict[str, Any]:
        return {
            "metadata": {
                "tools": span_data.tools,
                "handoffs": span_data.handoffs,
                "output_type": span_data.output_type,
            }
        }

    def _extract_handoff_span_data(
        span_data: tracing.HandoffSpanData,
    ) -> Dict[str, Any]:
        return {
            "metadata": {
                "from_agent": span_data.from_agent,
                "to_agent": span_data.to_agent,
            }
        }

    def _extract_guardrail_span_data(
        span_data: tracing.GuardrailSpanData,
    ) -> Dict[str, Any]:
        return {"metadata": {"triggered": span_data.triggered}}

    def _extract_custom_span_data(span_data: tracing.CustomSpanData) -> Dict[str, Any]:
        return {"metadata": span_data.data}

    def extract_span_data(span: tracing.Span) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        if isinstance(span.span_data, tracing.FunctionSpanData):
            data.update(_extract_function_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.GenerationSpanData):
            data.update(_extract_generation_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.ResponseSpanData):
            data.update(_extract_response_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.AgentSpanData):
            data.update(_extract_agent_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.HandoffSpanData):
            data.update(_extract_handoff_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.GuardrailSpanData):
            data.update(_extract_guardrail_span_data(span.span_data))
        elif isinstance(span.span_data, tracing.CustomSpanData):
            data.update(_extract_custom_span_data(span.span_data))
        else:
            return {}

        return data
