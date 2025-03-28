import datetime
import logging
import uuid
import warnings
from typing import Any, Dict, Optional, cast

from langsmith import run_trees as rt
from langsmith.run_helpers import _VALID_RUN_TYPES

try:
    from agents import tracing  # type: ignore[import]

    import langsmith.wrappers._agent_utils as agent_utils

    HAVE_AGENTS = True
except ImportError:
    HAVE_AGENTS = False

    class OpenAIAgentsTracingProcessor:
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

        def __init__(
            self,
            client: Optional[ls_client.Client] = None,
            langsmith_extra: Optional[Dict[str, Any]] = None,
        ):
            self.client = client or rt.get_cached_client()
            self._runs: Dict[str, str] = {}
            self._langsmith_extra = (
                self._validate_langsmith_extra(langsmith_extra)
                if langsmith_extra
                else {}
            )

        def _validate_langsmith_extra(self, extra: Dict[str, Any]) -> Dict[str, Any]:
            allowed_keys = {
                "name",
                "metadata",
                "tags",
                "project_name",
                "client",
                "run_type",
            }
            filtered_extra = {k: v for k, v in extra.items() if k in allowed_keys}
            invalid_keys = set(extra.keys()) - allowed_keys
            if invalid_keys:
                logger.warning(
                    f"Invalid keys in langsmith_extra will be ignored: {invalid_keys}. "
                    f"Allowed keys are: {allowed_keys}"
                )
            if "run_type" in filtered_extra:
                run_type = cast(ls_client.RUN_TYPE_T, filtered_extra["run_type"])
                if run_type not in _VALID_RUN_TYPES:
                    warnings.warn(
                        f"Unrecognized run_type: {run_type}. "
                        f"Must be one of: {_VALID_RUN_TYPES}."
                        f" Did you mean to use a different name instead?"
                    )
                    filtered_extra.pop("run_type")
            if "metadata" in filtered_extra:
                metadata = filtered_extra.pop("metadata")
                if not isinstance(metadata, dict):
                    warnings.warn(
                        f"metadata must be a dictionary, got {type(metadata)}. "
                    )
                    metadata = {}
                filtered_extra["extra"] = {"metadata": metadata}

            return filtered_extra

        def on_trace_start(self, trace: tracing.Trace) -> None:
            run_name = trace.name if trace.name else "Agent workflow"
            trace_run_id = str(uuid.uuid4())
            self._runs[trace.trace_id] = trace_run_id

            try:
                run_data: dict = dict(
                    inputs={},
                    id=trace_run_id,
                    revision_id=None,
                )
                if "name" not in self._langsmith_extra:
                    run_data["name"] = run_name
                if "run_type" not in self._langsmith_extra:
                    run_data["run_type"] = "chain"
                self.client.create_run(**run_data, **self._langsmith_extra)
            except Exception as e:
                logger.exception(f"Error creating trace run: {e}")

        def on_trace_end(self, trace: tracing.Trace) -> None:
            run_id = self._runs.pop(trace.trace_id, None)
            trace_dict = trace.export() or {}
            metadata = trace_dict.get("metadata") or {}
            if run_id:
                try:
                    # Merge with existing metadata if present
                    if (
                        "extra" in self._langsmith_extra
                        and "metadata" in self._langsmith_extra["extra"]
                    ):
                        user_metadata = self._langsmith_extra["extra"]["metadata"]
                        metadata.update(user_metadata)
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
                    id=span_run_id,
                    parent_run_id=parent_run_id,
                    inputs=extracted.get("inputs", {}),
                )
                if "name" not in self._langsmith_extra:
                    run_data["name"] = run_name
                if "run_type" not in self._langsmith_extra:
                    run_data["run_type"] = run_type
                if span.started_at:
                    run_data["start_time"] = datetime.datetime.fromisoformat(
                        span.started_at
                    )
                self.client.create_run(**run_data, **self._langsmith_extra)
            except Exception as e:
                logger.exception(f"Error creating span run: {e}")

        def on_span_end(self, span: tracing.Span) -> None:
            run_id = self._runs.pop(span.span_id, None)
            if run_id:
                extracted = agent_utils.extract_span_data(span)
                metadata = extracted.get("metadata", {})

                # Add OpenAI span IDs to metadata
                metadata["openai_parent_id"] = span.parent_id
                metadata["openai_trace_id"] = span.trace_id
                metadata["openai_span_id"] = span.span_id

                # Merge with existing metadata from langsmith_extra if it exists
                if (
                    "extra" in self._langsmith_extra
                    and "metadata" in self._langsmith_extra["extra"]
                ):
                    user_metadata = self._langsmith_extra["extra"]["metadata"]
                    metadata.update(user_metadata)
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
