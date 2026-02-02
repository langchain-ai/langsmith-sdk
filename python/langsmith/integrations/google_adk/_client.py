"""Client instrumentation for Google ADK."""

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree, trace

from ._config import get_tracing_config
from ._hooks import clear_active_runs
from ._recursive import RecursiveCallbackInjector, get_callbacks
from ._tools import clear_parent_run_tree, set_parent_run_tree

logger = logging.getLogger(__name__)

DEBUG_TRACE_DATA = False  # Set to True to log trace inputs/outputs


def _extract_text_from_content(content: Any) -> str | None:
    """Extract plain text from ADK Content object.

    Args:
        content: ADK Content object with parts.

    Returns:
        The concatenated text from all text parts, or None.
    """
    if content is None:
        return None

    # Get parts from Content object
    parts = getattr(content, "parts", None)
    if not parts:
        return None

    text_parts = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            text_parts.append(str(text))

    return " ".join(text_parts) if text_parts else None


def _serialize_for_trace(obj: Any) -> Any:
    """Serialize ADK object for trace input/output.

    Uses model_dump() for Pydantic models (like Opik/Braintrust do),
    otherwise returns as-is or converts to string.

    Args:
        obj: Any object to serialize.

    Returns:
        JSON-serializable representation.
    """
    if obj is None:
        return None

    # ADK Content objects are Pydantic models - use model_dump()
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return obj.model_dump(exclude_none=True, mode="json")
        except Exception:
            pass

    # Already serializable types
    if isinstance(obj, (str, int, float, bool, list, dict)):
        return obj

    # Fallback to string
    return str(obj)

TRACE_CHAIN_NAME = "google_adk.session"


def _inject_tracing_callbacks(agent: Any) -> None:
    """Inject LangSmith tracing callbacks into an agent hierarchy.

    This uses RecursiveCallbackInjector to traverse the entire agent
    hierarchy and inject callbacks at every level.

    Args:
        agent: The root agent to inject callbacks into.
    """
    try:
        callbacks = get_callbacks()
        injector = RecursiveCallbackInjector(callbacks)
        injector.inject(agent)
        logger.debug("Injected LangSmith tracing callbacks into agent hierarchy")
    except Exception as e:
        logger.warning(f"Failed to inject tracing callbacks: {e}")


def instrument_adk_runner(original_class: Any) -> Any:
    """Wrap `Runner` to auto-inject LangSmith callbacks and trace sessions.

    Args:
        original_class: The original Runner class to wrap.

    Returns:
        A wrapped Runner class with tracing enabled.
    """

    class TracedRunner(original_class):
        """Runner subclass that automatically traces all sessions."""

        def __init__(self, *args: Any, **kwargs: Any):
            if DEBUG_TRACE_DATA:
                logger.debug(f"TracedRunner.__init__ called with args={args}, kwargs keys={kwargs.keys()}")

            # Get the agent from kwargs or args
            agent = kwargs.get("agent")
            if not agent and args:
                # First positional arg might be agent
                agent = args[0] if args else None

            # Inject tracing callbacks into the agent hierarchy
            if agent:
                _inject_tracing_callbacks(agent)

            super().__init__(*args, **kwargs)

            # Store configuration for tracing
            self._langsmith_config = get_tracing_config()
            self._trace_start_time: Optional[float] = None

        def run(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            """Run the agent synchronously with tracing."""
            if DEBUG_TRACE_DATA:
                logger.debug(f"TracedRunner.run() called")

            config = self._langsmith_config
            trace_name = config.get("name") or TRACE_CHAIN_NAME

            # Extract session info for metadata
            user_id = kwargs.get("user_id")
            session_id = kwargs.get("session_id")
            new_message = kwargs.get("new_message")

            # Use flat text input, not nested parts
            trace_inputs: dict[str, Any] = {}
            if new_message:
                input_text = _extract_text_from_content(new_message)
                if input_text:
                    trace_inputs["input"] = input_text

            # Put session info in metadata, not inputs
            trace_metadata = {
                **(config.get("metadata") or {}),
            }
            if hasattr(self, "app_name") and self.app_name:
                trace_metadata["app_name"] = self.app_name
            if user_id:
                trace_metadata["user_id"] = user_id
            if session_id:
                trace_metadata["session_id"] = session_id

            self._trace_start_time = time.time()

            if DEBUG_TRACE_DATA:
                logger.debug(
                    f"Root span inputs: {json.dumps(trace_inputs, indent=2)}"
                )
                logger.debug(
                    f"Root span metadata: {json.dumps(trace_metadata, indent=2)}"
                )

            with trace(
                name=trace_name,
                run_type="chain",
                inputs=trace_inputs,
                project_name=config.get("project_name"),
                tags=config.get("tags"),
                metadata=trace_metadata,
            ) as run:
                set_parent_run_tree(run)
                try:
                    # super().run() returns a generator - consume it
                    result_generator = super().run(*args, **kwargs)
                    events = list(result_generator)

                    # Extract final text output from last event with model content
                    final_output = None
                    for event in reversed(events):
                        content = getattr(event, "content", None)
                        if content:
                            final_output = _extract_text_from_content(content)
                            if final_output:
                                break

                    outputs = {"output": final_output} if final_output else None
                    run.end(outputs=outputs)

                    # Return a generator-like object for compatibility
                    return iter(events)
                except Exception as e:
                    run.end(error=str(e))
                    raise
                finally:
                    clear_parent_run_tree()
                    clear_active_runs()

        async def run_async(
            self,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[Any, None]:
            """Async run with tracing that yields events."""
            config = self._langsmith_config
            trace_name = config.get("name") or TRACE_CHAIN_NAME

            # Extract session info for metadata
            user_id = kwargs.get("user_id")
            session_id = kwargs.get("session_id")
            new_message = kwargs.get("new_message")

            # Use flat text input, not nested parts
            trace_inputs: dict[str, Any] = {}
            if new_message:
                input_text = _extract_text_from_content(new_message)
                if input_text:
                    trace_inputs["input"] = input_text

            # Put session info in metadata, not inputs
            trace_metadata = {
                **(config.get("metadata") or {}),
            }
            if hasattr(self, "app_name") and self.app_name:
                trace_metadata["app_name"] = self.app_name
            if user_id:
                trace_metadata["user_id"] = user_id
            if session_id:
                trace_metadata["session_id"] = session_id

            self._trace_start_time = time.time()
            final_output: str | None = None

            async with trace(
                name=trace_name,
                run_type="chain",
                inputs=trace_inputs,
                project_name=config.get("project_name"),
                tags=config.get("tags"),
                metadata=trace_metadata,
            ) as run:
                set_parent_run_tree(run)
                try:
                    # Call parent's run_async and yield events
                    async for event in super().run_async(*args, **kwargs):
                        # Track the final text output from events
                        content = getattr(event, "content", None)
                        if content:
                            text = _extract_text_from_content(content)
                            if text:
                                final_output = text
                        yield event

                    outputs = {"output": final_output} if final_output else None
                    run.end(outputs=outputs)
                except Exception as e:
                    run.end(error=str(e))
                    raise
                finally:
                    clear_parent_run_tree()
                    clear_active_runs()

        def _get_trace_run(self) -> Any:
            """Get the current trace run for manual updates.

            Returns:
                The current RunTree or None.
            """
            return get_current_run_tree()

    return TracedRunner


def create_traced_session_context(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    inputs: Optional[dict[str, Any]] = None,
):
    """Create a trace context for manual session tracing.

    Use this when you want more control over the tracing context,
    or when using the Runner without the automatic instrumentation.

    Args:
        name: Name of the trace.
        project_name: LangSmith project name.
        metadata: Additional metadata.
        tags: Tags for the trace.
        inputs: Initial inputs for the trace.

    Returns:
        A trace context manager.

    Example:
        ```python
        async with create_traced_session_context(
            name="my_session", project_name="my-project"
        ) as run:
            # Run your ADK agent here
            pass
        ```
    """
    config = get_tracing_config()

    trace_name = name or config.get("name") or TRACE_CHAIN_NAME
    trace_project = project_name or config.get("project_name")
    trace_tags = tags or config.get("tags")
    trace_metadata = {
        **(config.get("metadata") or {}),
        **(metadata or {}),
    }

    return trace(
        name=trace_name,
        run_type="chain",
        inputs=inputs or {},
        project_name=trace_project,
        tags=trace_tags,
        metadata=trace_metadata,
    )
