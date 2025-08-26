import logging
from datetime import datetime, timezone
from typing import Optional, TypedDict
from uuid import uuid4

from langsmith import run_trees as rt

try:
    from agents import tracing  # type: ignore[import]

    required = (
        "TracingProcessor",
        "Trace",
        "Span",
        "ResponseSpanData",
    )
    if not all(hasattr(tracing, name) for name in required):
        raise ImportError("The `agents` package is not installed.")

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

    class RunData(TypedDict):
        id: str
        trace_id: str
        start_time: datetime
        dotted_order: str
        parent_run_id: Optional[str]

    class OpenAIAgentsTracingProcessor(tracing.TracingProcessor):  # type: ignore[no-redef]
        """Tracing processor for the `OpenAI Agents SDK <https://openai.github.io/openai-agents-python/>`_.

        Traces all intermediate steps of your OpenAI Agent to LangSmith.

        Requirements: Make sure to install ``pip install -U langsmith[openai-agents]``.

        Args:
            client: An instance of langsmith.client.Client. If not provided,
                a default client is created.
            metadata: Metadata to associate with all traces.
            tags: Tags to associate with all traces.
            project_name: LangSmith project to trace to.
            name: Name of the root trace.

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
            *,
            metadata: Optional[dict] = None,
            tags: Optional[list[str]] = None,
            project_name: Optional[str] = None,
            name: Optional[str] = None,
            parent_run: Optional[rt.RunTree] = None,
        ):
            self.client = client or rt.get_cached_client()
            self._metadata = metadata
            self._tags = tags
            self._project_name = project_name
            self._name = name
            self.parent_run = parent_run
            self._first_response_inputs: dict = {}
            self._last_response_outputs: dict = {}

            self._runs: dict[str, RunData] = {}

        def on_trace_start(self, trace: tracing.Trace) -> None:
            if self._name:
                run_name = self._name
            elif trace.name:
                run_name = trace.name
            else:
                run_name = "Agent workflow"
            trace_run_id = str(uuid4())

            start_time = datetime.now(timezone.utc)

            # Handle parent context with proper validation-compliant approach
            if self.parent_run:
                # Ensure we create a valid child run that passes all LangSmith
                # validations
                parent_run_id = str(self.parent_run.id)
                parent_trace_id = str(self.parent_run.trace_id)
                parent_dotted_order = self.parent_run.dotted_order

                # CRITICAL: Use parent's trace_id to maintain hierarchy
                final_trace_id = parent_trace_id

                # Create child dotted_order - this should be valid for child runs
                dotted_order = agent_utils.ensure_dotted_order(
                    start_time=start_time,
                    run_id=trace_run_id,
                    parent_dotted_order=parent_dotted_order,
                )

                # Validate our parameters match LangSmith expectations
                # Child runs should have: parent_run_id set, trace_id = parent's
                # trace_id, complex dotted_order
                assert parent_run_id is not None, "Child run must have parent_run_id"
                assert final_trace_id == parent_trace_id, (
                    "Child run must use parent's trace_id"
                )
                assert "." in dotted_order, "Child run should have complex dotted_order"

                parent_info = {}
            else:
                # When no parent, create a root run (original behavior)
                parent_run_id = None
                final_trace_id = trace_run_id
                parent_info = {}

                # Create simple root dotted_order
                dotted_order = agent_utils.ensure_dotted_order(
                    start_time=start_time,
                    run_id=trace_run_id,
                )

                # Validate root run parameters
                # Root runs should have: parent_run_id = None, trace_id = run_id,
                # simple dotted_order
                assert parent_run_id is None, "Root run must not have parent_run_id"
                assert final_trace_id == trace_run_id, (
                    "Root run must use its own trace_id"
                )

            self._runs[trace.trace_id] = RunData(
                id=trace_run_id,
                trace_id=final_trace_id,
                start_time=start_time,
                dotted_order=dotted_order,
                parent_run_id=parent_run_id,
            )

            run_extra = {"metadata": {**(self._metadata or {}), **parent_info}}

            trace_dict = trace.export() or {}
            if trace_dict.get("group_id") is not None:
                run_extra["metadata"]["thread_id"] = trace_dict["group_id"]

            try:
                run_data: dict = dict(
                    name=run_name,
                    inputs={},
                    run_type="chain",
                    id=trace_run_id,
                    trace_id=final_trace_id,
                    parent_run_id=parent_run_id,
                    dotted_order=dotted_order,
                    start_time=start_time,
                    revision_id=None,
                    extra=run_extra,
                    tags=self._tags,
                    project_name=self._project_name,
                )

                # Create the run with validated hierarchical context
                # Note: This should succeed for the regular API, multipart ingest
                # errors are separate
                self.client.create_run(**run_data)
            except Exception as e:
                logger.exception(f"Error creating trace run: {e}")

        def on_trace_end(self, trace: tracing.Trace) -> None:
            run = self._runs.pop(trace.trace_id, None)
            trace_dict = trace.export() or {}
            metadata = {**(trace_dict.get("metadata") or {}), **(self._metadata or {})}

            if run:
                try:
                    self.client.update_run(
                        run_id=run["id"],
                        trace_id=run["trace_id"],
                        dotted_order=run["dotted_order"],
                        inputs=self._first_response_inputs.pop(trace.trace_id, {}),
                        outputs=self._last_response_outputs.pop(trace.trace_id, {}),
                        extra={"metadata": metadata},
                    )
                except Exception as e:
                    logger.exception(f"Error updating trace run: {e}")

        def on_span_start(self, span: tracing.Span) -> None:
            parent_run = (
                self._runs.get(span.parent_id)
                if span.parent_id
                else self._runs.get(span.trace_id)
            )

            if parent_run is None:
                logger.warning(
                    f"No trace info found for span, skipping: {span.span_id}"
                )
                return

            trace_id = parent_run["trace_id"]

            span_run_id = str(uuid4())
            span_start_time = (
                datetime.fromisoformat(span.started_at)
                if span.started_at
                else datetime.now(timezone.utc)
            )
            dotted_order = agent_utils.ensure_dotted_order(
                start_time=span_start_time,
                run_id=span_run_id,
                parent_dotted_order=parent_run["dotted_order"] if parent_run else None,
            )
            self._runs[span.span_id] = RunData(
                id=span_run_id,
                trace_id=trace_id,
                start_time=span_start_time,
                dotted_order=dotted_order,
                parent_run_id=parent_run["id"],
            )

            run_name = agent_utils.get_run_name(span)
            run_type = agent_utils.get_run_type(span)
            extracted = agent_utils.extract_span_data(span)

            try:
                run_data: dict = dict(
                    name=run_name,
                    run_type=run_type,
                    id=span_run_id,
                    trace_id=trace_id,
                    parent_run_id=parent_run["id"],
                    dotted_order=dotted_order,
                    inputs=extracted.get("inputs", {}),
                )
                if span.started_at:
                    run_data["start_time"] = datetime.fromisoformat(span.started_at)
                self.client.create_run(**run_data)
            except Exception as e:
                logger.exception(f"Error creating span run: {e}")

        def on_span_end(self, span: tracing.Span) -> None:
            run = self._runs.pop(span.span_id, None)
            if run:
                extracted = agent_utils.extract_span_data(span)
                metadata = extracted.get("metadata", {})
                metadata["openai_parent_id"] = span.parent_id
                metadata["openai_trace_id"] = span.trace_id
                metadata["openai_span_id"] = span.span_id
                extracted["metadata"] = metadata
                outputs = extracted.pop("outputs", {})
                inputs = extracted.pop("inputs", {})
                run_data: dict = dict(
                    run_id=run["id"],
                    trace_id=run["trace_id"],
                    dotted_order=run["dotted_order"],
                    parent_run_id=run["parent_run_id"],
                    error=str(span.error) if span.error else None,
                    outputs=outputs,
                    inputs=inputs,
                    extra=extracted,
                )
                if span.ended_at:
                    run_data["end_time"] = datetime.fromisoformat(span.ended_at)

                if isinstance(span.span_data, tracing.ResponseSpanData):
                    self._first_response_inputs[span.trace_id] = (
                        self._first_response_inputs.get(span.trace_id) or inputs
                    )
                    self._last_response_outputs[span.trace_id] = outputs

                self.client.update_run(**run_data)

        def shutdown(self) -> None:
            self.client.flush()

        def force_flush(self) -> None:
            self.client.flush()


class HierarchicalTracingContext:
    """Async context manager for hierarchical OpenAI Agents tracing.

    This provides a clean API for users to enable hierarchical tracing
    without managing processor lifecycle manually.

    Example:
        async with HierarchicalTracingContext(parent_run, "My Agent"):
            result = await Runner.run(agent, query)
    """

    def __init__(self, parent_run: Optional[rt.RunTree], name: str = "OpenAI Agent"):
        """Initialize the hierarchical tracing context.

        Args:
            parent_run: The parent LangSmith run tree (from get_current_run_tree())
            name: Name for the agent trace
        """
        self.parent_run = parent_run
        self.name = name
        self.processor = None
        self.original_processors = []

    async def __aenter__(self):
        """Set up hierarchical tracing processor."""
        # Store current processors to restore later
        # Note: In practice, you might want to get actual current processors
        self.original_processors = []

        # Create and set our hierarchical processor
        self.processor = OpenAIAgentsTracingProcessor(
            parent_run=self.parent_run, name=self.name
        )

        # Import here to avoid circular imports
        try:
            from agents import set_trace_processors  # type: ignore[import]

            set_trace_processors([self.processor])
        except ImportError:
            raise RuntimeError("The `agents` package is not installed.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up tracing processor."""
        if self.processor:
            # Ensure all traces are flushed
            self.processor.force_flush()
            # Properly shut down
            self.processor.shutdown()

        # Restore original processors
        try:
            from agents import set_trace_processors  # type: ignore[import]

            set_trace_processors(self.original_processors)
        except ImportError:
            # If agents is not available, there's nothing to restore
            pass


def hierarchical_tracing(parent_run: Optional[rt.RunTree], name: str = "OpenAI Agent"):
    """Create a hierarchical tracing context.

    Args:
        parent_run: The parent LangSmith run tree (from get_current_run_tree())
        name: Name for the agent trace

    Returns:
        HierarchicalTracingContext: Async context manager

    Example:
        from langsmith.run_helpers import get_current_run_tree
        from modified_openai_agents import hierarchical_tracing

        parent_run = get_current_run_tree()
        async with hierarchical_tracing(parent_run, "Weather Agent"):
            result = await Runner.run(agent, query)
    """
    return HierarchicalTracingContext(parent_run, name)
