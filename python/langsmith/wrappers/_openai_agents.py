import logging
import uuid
from typing import Any, Dict, Literal, Optional

try:
    from agents import tracing  # type: ignore[import]

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

from langsmith import client as ls_client

logger = logging.getLogger(__name__)

RunTypeT = Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]


def _get_run_type(span: tracing.Span) -> RunTypeT:
    span_type = getattr(span.span_data, "type", None)
    if span_type in ["agent", "handoff", "custom"]:
        return "chain"
    elif span_type in ["function", "guardrail"]:
        return "tool"
    elif span_type in ["generation", "response"]:
        return "llm"
    else:
        return "chain"


def _get_run_name(span: tracing.Span) -> str:
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


def _extract_function_span_data(span_data: tracing.FunctionSpanData) -> Dict[str, Any]:
    return {"inputs": span_data.input, "outputs": span_data.output}


def _extract_generation_span_data(
    span_data: tracing.GenerationSpanData,
) -> Dict[str, Any]:
    data = {
        "inputs": span_data.input,
        "outputs": span_data.output,
        "metadata": {"model": span_data.model, "model_config": span_data.model_config},
    }
    if span_data.usage:
        data["usage_metadata"] = {
            "total_tokens": span_data.usage.get("total_tokens"),
            "input_tokens": span_data.usage.get("prompt_tokens"),
            "output_tokens": span_data.usage.get("completion_tokens"),
        }
    return data


def _extract_response_span_data(span_data: tracing.ResponseSpanData) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if span_data.input is not None:
        data["inputs"] = {"messages": list(span_data.input)}
    if span_data.response is not None:
        data["outputs"] = {
            "messages": [output.model_dump() for output in span_data.response.output]
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


def _extract_handoff_span_data(span_data: tracing.HandoffSpanData) -> Dict[str, Any]:
    return {
        "metadata": {"from_agent": span_data.from_agent, "to_agent": span_data.to_agent}
    }


def _extract_guardrail_span_data(
    span_data: tracing.GuardrailSpanData,
) -> Dict[str, Any]:
    return {"metadata": {"triggered": span_data.triggered}}


def _extract_custom_span_data(span_data: tracing.CustomSpanData) -> Dict[str, Any]:
    return {"metadata": span_data.data}


def _extract_span_data(span: tracing.Span) -> Dict[str, Any]:
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


class LangsmithTracingProcessor(tracing.TracingProcessor):
    """LangsmithTracingProcessor is a TracingProcessor for the OpenAI Agents SDK.

    It logs traces and spans to Langsmith.

    Args:
        client: An instance of langsmith.client.Client. If not provided,
            a default client is created.
    """

    def __init__(self, client: Optional[ls_client.Client] = None):
        self.client = client or ls_client.Client()
        self._runs: Dict[str, str] = {}
        if not HAVE_AGENTS:
            raise ImportError(
                "The `agents` package is not installed. "
                "Please install it with `pip install langsmith[openai-agents]`."
            )

    def on_trace_start(self, trace: tracing.Trace) -> None:
        run_name = trace.name if trace.name else "Agent trace"
        trace_run_id = str(uuid.uuid4())
        self._runs[trace.trace_id] = trace_run_id

        try:
            run_data: dict = dict(
                name=run_name,
                inputs={},
                run_type="chain",
                id=trace_run_id,
                revision_id=None,
            )
            self.client.create_run(**run_data)
        except Exception as e:
            logger.error(f"Error creating trace run: {e}")

    def on_trace_end(self, trace: tracing.Trace) -> None:
        run_id = self._runs.pop(trace.trace_id, None)
        if run_id:
            try:
                self.client.update_run(
                    run_id=run_id,
                )
            except Exception as e:
                logger.error(f"Error updating trace run: {e}")

    def on_span_start(self, span: tracing.Span) -> None:
        parent_run_id = None
        if span.parent_id:
            parent_run_id = self._runs.get(span.parent_id)
        else:
            parent_run_id = self._runs.get(span.trace_id)
        span_run_id = str(uuid.uuid4())
        self._runs[span.span_id] = span_run_id

        run_name = _get_run_name(span)
        run_type = _get_run_type(span)

        try:
            run_data: dict = dict(
                name=run_name,
                run_type=run_type,
                id=span_run_id,
                parent_run_id=parent_run_id,
                inputs={},
            )
            self.client.create_run(**run_data)
        except Exception as e:
            logger.error(f"Error creating span run: {e}")

    def on_span_end(self, span: tracing.Span) -> None:
        run_id = self._runs.pop(span.span_id, None)
        if run_id:
            extracted = _extract_span_data(span)
            run_data: dict = dict(
                run_id=run_id,
                error=span.error,
                inputs=extracted.get("inputs", {}),
                outputs=extracted.get("outputs", {}),
                extra={"metadata": extracted.get("metadata", {})},
            )
            self.client.update_run(**run_data)

    def shutdown(self) -> None:
        if self.client is not None:
            self.client.flush()
        else:
            logger.warning("No client to flush")

    def force_flush(self) -> None:
        if self.client is not None:
            self.client.flush()
        else:
            logger.warning("No client to flush")
