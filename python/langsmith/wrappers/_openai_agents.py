import datetime
import logging
import uuid
from typing import Dict, Optional

from langsmith import run_trees as rt

try:
    from agents import tracing  # type: ignore[import]

    import langsmith.wrappers._agent_utils as agent_utils

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

    class OpenAIAgentsTracingProcessor:
        """Stub class when agents package is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "The `agents` package is not installed. "
                "Please install it with `pip install langsmith[openai-agents]`."
            )


from langsmith import client as ls_client

logger = logging.getLogger(__name__)

if HAVE_AGENTS:

    class OpenAIAgentsTracingProcessor(tracing.TracingProcessor):  # type: ignore[no-redef]
        """Tracing processor for the `OpenAI Agents SDK <https://openai.github.io/openai-agents-python/>`_.

        Traces all intermediate steps of your OpenAI Agent to LangSmith.

        Requirements: Make sure to install ``pip install -U langsmith[openai-agents]``.

        Args:
            client: An instance of langsmith.client.Client. If not provided,
                a default client is created.

        Example:
            .. code-block:: python

                from agents import (
                    Agent,
                    FileSearchTool,
                    Runner,
                    WebSearchTool,
                    function_tool,
                    set_trace_processors,
                )

                from langsmith.wrappers import OpenAIAgentsTracingProcessor

                set_trace_processors([OpenAIAgentsTracingProcessor()])


                @function_tool
                def get_weather(city: str) -> str:
                    return f"The weather in {city} is sunny"


                haiku_agent = Agent(
                    name="Haiku agent",
                    instructions="Always respond in haiku form",
                    model="o3-mini",
                    tools=[get_weather],
                )
                agent = Agent(
                    name="Assistant",
                    tools=[WebSearchTool()],
                    instructions="speak in spanish. use Haiku agent if they ask for a haiku or for the weather",
                    handoffs=[haiku_agent],
                )

                result = await Runner.run(
                    agent,
                    "write a haiku about the weather today and tell me a recent news story about new york",
                )
                print(result.final_output)
        """  # noqa: E501

        def __init__(self, client: Optional[ls_client.Client] = None):
            self.client = client or rt.get_cached_client()
            self._runs: Dict[str, str] = {}

        def on_trace_start(self, trace: tracing.Trace) -> None:
            run_name = trace.name if trace.name else "Agent workflow"
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
                logger.exception(f"Error creating trace run: {e}")

        def on_trace_end(self, trace: tracing.Trace) -> None:
            run_id = self._runs.pop(trace.trace_id, None)
            trace_dict = trace.export() or {}
            metadata = trace_dict.get("metadata") or {}
            if run_id:
                try:
                    self.client.update_run(run_id=run_id, extra={"metadata": metadata})
                except Exception as e:
                    logger.exception(f"Error updating trace run: {e}")

        def on_span_start(self, span: tracing.Span) -> None:
            parent_run_id = self._runs.get(span.parent_id or span.trace_id)
            span_run_id = str(uuid.uuid4())
            self._runs[span.span_id] = span_run_id

            run_name = agent_utils.get_run_name(span)
            run_type = agent_utils.get_run_type(span)
            extracted = agent_utils.extract_span_data(span)

            try:
                run_data: dict = dict(
                    name=run_name,
                    run_type=run_type,
                    id=span_run_id,
                    parent_run_id=parent_run_id,
                    inputs=extracted.get("inputs", {}),
                )
                if span.started_at:
                    run_data["start_time"] = datetime.datetime.fromisoformat(
                        span.started_at
                    )
                self.client.create_run(**run_data)
            except Exception as e:
                logger.exception(f"Error creating span run: {e}")

        def on_span_end(self, span: tracing.Span) -> None:
            run_id = self._runs.pop(span.span_id, None)
            if run_id:
                extracted = agent_utils.extract_span_data(span)
                metadata = extracted.get("metadata", {})
                metadata["openai_parent_id"] = span.parent_id
                metadata["openai_trace_id"] = span.trace_id
                metadata["openai_span_id"] = span.span_id
                extracted["metadata"] = metadata
                run_data: dict = dict(
                    run_id=run_id,
                    error=str(span.error) if span.error else None,
                    outputs=extracted.pop("outputs", {}),
                    inputs=extracted.pop("inputs", {}),
                    extra=extracted,
                )
                if span.ended_at:
                    run_data["end_time"] = datetime.datetime.fromisoformat(
                        span.ended_at
                    )
                self.client.update_run(**run_data)

        def shutdown(self) -> None:
            self.client.flush()

        def force_flush(self) -> None:
            self.client.flush()
