"""Client instrumentation for Google ADK.

Uses wrapt for import-order agnostic patching while maintaining
the 6 ADK callbacks for actual tracing.
"""

import json
import logging
import time
from contextlib import aclosing
from datetime import datetime, timezone
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree, trace
from langsmith.run_trees import RunTree

from ._config import get_tracing_config
from ._hooks import clear_active_runs
from ._messages import convert_llm_request_to_messages, has_function_calls
from ._recursive import RecursiveCallbackInjector, get_callbacks
from ._tools import clear_parent_run_tree, get_parent_run_tree, set_parent_run_tree
from ._usage import extract_model_name, extract_usage_from_response

logger = logging.getLogger(__name__)

TRACE_CHAIN_NAME = "google_adk.session"


def _extract_text_from_content(content: Any) -> str | None:
    """Extract plain text from ADK Content object."""
    if content is None:
        return None

    parts = getattr(content, "parts", None)
    if not parts:
        return None

    text_parts = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            text_parts.append(str(text))

    return " ".join(text_parts) if text_parts else None


def _inject_tracing_callbacks(agent: Any) -> None:
    """Inject LangSmith tracing callbacks into an agent hierarchy."""
    try:
        callbacks = get_callbacks()
        injector = RecursiveCallbackInjector(callbacks)
        injector.inject(agent)
        logger.debug("Injected LangSmith tracing callbacks into agent hierarchy")
    except Exception as e:
        logger.warning(f"Failed to inject tracing callbacks: {e}")


# =============================================================================
# Wrapt-style wrapper functions (for import-order agnostic patching)
# =============================================================================


def wrap_runner_init(wrapped: Any, instance: Any, args: Any, kwargs: Any) -> Any:
    """Wrapt wrapper for Runner.__init__ - injects callbacks into agent."""
    # Get the agent from kwargs or args
    agent = kwargs.get("agent")
    if not agent and args:
        agent = args[0] if args else None

    # Inject tracing callbacks into the agent hierarchy
    if agent:
        _inject_tracing_callbacks(agent)

    # Store config reference on instance for later use
    result = wrapped(*args, **kwargs)
    instance._langsmith_config = get_tracing_config()
    return result


def wrap_runner_run(wrapped: Any, instance: Any, args: Any, kwargs: Any) -> Any:
    """Wrapt wrapper for Runner.run - traces synchronous execution."""
    config = getattr(instance, "_langsmith_config", None) or get_tracing_config()
    trace_name = config.get("name") or TRACE_CHAIN_NAME

    # Extract session info
    user_id = kwargs.get("user_id")
    session_id = kwargs.get("session_id")
    new_message = kwargs.get("new_message")

    # Use flat text input
    trace_inputs: dict[str, Any] = {}
    if new_message:
        input_text = _extract_text_from_content(new_message)
        if input_text:
            trace_inputs["input"] = input_text

    # Put session info in metadata
    trace_metadata = {
        **(config.get("metadata") or {}),
    }
    if hasattr(instance, "app_name") and instance.app_name:
        trace_metadata["app_name"] = instance.app_name
    if user_id:
        trace_metadata["user_id"] = user_id
    if session_id:
        trace_metadata["session_id"] = session_id

    def _trace_run():
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
                # Consume the generator to get all events
                events = list(wrapped(*args, **kwargs))

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

                # Yield events for caller
                yield from events
            except Exception as e:
                run.end(error=str(e))
                raise
            finally:
                clear_parent_run_tree()
                clear_active_runs()

    return _trace_run()


async def wrap_runner_run_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrapt wrapper for Runner.run_async - traces async execution with aclosing."""
    config = getattr(instance, "_langsmith_config", None) or get_tracing_config()
    trace_name = config.get("name") or TRACE_CHAIN_NAME

    # Extract session info
    user_id = kwargs.get("user_id")
    session_id = kwargs.get("session_id")
    new_message = kwargs.get("new_message")

    # Use flat text input
    trace_inputs: dict[str, Any] = {}
    if new_message:
        input_text = _extract_text_from_content(new_message)
        if input_text:
            trace_inputs["input"] = input_text

    # Put session info in metadata
    trace_metadata = {
        **(config.get("metadata") or {}),
    }
    if hasattr(instance, "app_name") and instance.app_name:
        trace_metadata["app_name"] = instance.app_name
    if user_id:
        trace_metadata["user_id"] = user_id
    if session_id:
        trace_metadata["session_id"] = session_id

    async def _trace_run_async():
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
                final_output: str | None = None

                # Use aclosing for proper async generator cleanup (like Braintrust)
                async with aclosing(wrapped(*args, **kwargs)) as agen:
                    async for event in agen:
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

    # Return the async generator
    async for event in _trace_run_async():
        yield event


# =============================================================================
# Flow-level wrapping for TTFT capture
# =============================================================================


def _get_parent_run() -> RunTree | None:
    """Get the parent run tree from thread-local or context."""
    return get_parent_run_tree() or get_current_run_tree()


def _determine_llm_call_type_from_response(llm_request: Any, llm_response: Any) -> str:
    """Classify LLM call based on request/response content."""
    try:
        # Check if there's a function_response in request contents
        contents = getattr(llm_request, "contents", None)
        if contents:
            for content in contents:
                parts = getattr(content, "parts", None)
                if parts:
                    for part in parts:
                        if hasattr(part, "function_response") and part.function_response:
                            return "response_generation"

        # Check if response has function calls
        if has_function_calls(llm_response):
            return "tool_selection"

        return "direct_response"
    except Exception:
        return "unknown"


async def wrap_flow_call_llm_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrapt wrapper for BaseLlmFlow._call_llm_async - captures TTFT via streaming.

    This wraps the low-level LLM call to capture time-to-first-token by observing
    the first event from the async generator.
    """
    parent = _get_parent_run()
    if not parent:
        # No tracing context, just pass through
        async for event in wrapped(*args, **kwargs):
            yield event
        return

    # Extract invocation_context and llm_request from args
    invocation_context = args[0] if len(args) > 0 else kwargs.get("invocation_context")
    llm_request = args[1] if len(args) > 1 else kwargs.get("llm_request")

    # Extract model name and messages for inputs
    model_name = extract_model_name(llm_request) if llm_request else None
    messages = convert_llm_request_to_messages(llm_request) if llm_request else None

    inputs: dict[str, Any] = {}
    if messages:
        inputs["messages"] = messages

    # Build metadata
    metadata: dict[str, Any] = {}
    if model_name:
        metadata["ls_model_name"] = model_name

    # Create LLM span
    start_time = time.time()
    llm_run = parent.create_child(
        name=model_name or "google_adk_llm",
        run_type="llm",
        inputs=inputs,
        extra={"metadata": metadata} if metadata else None,
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
    )

    try:
        llm_run.post()
    except Exception as e:
        logger.debug(f"Failed to post LLM run: {e}")

    first_token_time: float | None = None
    last_event = None
    event_with_content = None

    try:
        async with aclosing(wrapped(*args, **kwargs)) as agen:
            async for event in agen:
                # Record TTFT on first event
                if first_token_time is None:
                    first_token_time = time.time()
                    try:
                        llm_run.add_event({
                            "name": "new_token",
                            "time": datetime.fromtimestamp(
                                first_token_time, tz=timezone.utc
                            ).isoformat(),
                        })
                    except Exception as e:
                        logger.debug(f"Failed to add new_token event: {e}")

                last_event = event
                if hasattr(event, "content") and event.content is not None:
                    event_with_content = event

                yield event

        # After execution, finalize the span
        outputs: dict[str, Any] = {"role": "assistant"}

        # Extract content from the best available event
        content_source = event_with_content or last_event
        if content_source and hasattr(content_source, "content") and content_source.content:
            content = content_source.content
            parts = getattr(content, "parts", None)
            if parts:
                text_parts = []
                tool_calls = []
                tool_call_idx = 0

                for part in parts:
                    if hasattr(part, "text") and part.text:
                        text_parts.append(str(part.text))
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        tool_calls.append({
                            "id": f"call_{tool_call_idx}",
                            "type": "function",
                            "function": {
                                "name": getattr(fc, "name", ""),
                                "arguments": json.dumps(
                                    dict(fc.args) if hasattr(fc, "args") and fc.args else {}
                                ),
                            },
                        })
                        tool_call_idx += 1

                if text_parts:
                    outputs["content"] = " ".join(text_parts)
                else:
                    outputs["content"] = None

                if tool_calls:
                    outputs["tool_calls"] = tool_calls

        # Extract usage metrics
        if last_event:
            usage = extract_usage_from_response(last_event)
            if usage:
                llm_run.extra.setdefault("metadata", {})["usage_metadata"] = usage

        # Add TTFT metric
        if first_token_time is not None:
            ttft = first_token_time - start_time
            llm_run.extra.setdefault("metadata", {})["time_to_first_token"] = ttft

        # Determine call type
        if last_event and llm_request:
            call_type = _determine_llm_call_type_from_response(llm_request, last_event)
            llm_run.extra.setdefault("metadata", {})["llm_call_type"] = call_type

        llm_run.end(outputs=outputs)
        try:
            llm_run.patch()
        except Exception as e:
            logger.debug(f"Failed to patch LLM run: {e}")

    except Exception as e:
        llm_run.end(error=str(e))
        try:
            llm_run.patch()
        except Exception:
            pass
        raise


# =============================================================================
# MCP Tool wrapping
# =============================================================================


async def wrap_mcp_tool_run_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrapt wrapper for McpTool.run_async - traces MCP tool invocations."""
    parent = _get_parent_run()
    if not parent:
        return await wrapped(*args, **kwargs)

    tool_name = getattr(instance, "name", "mcp_tool")
    tool_args = kwargs.get("args", {})

    start_time = time.time()
    tool_run = parent.create_child(
        name=f"mcp_tool [{tool_name}]",
        run_type="tool",
        inputs={"tool_name": tool_name, "arguments": tool_args},
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
    )

    try:
        tool_run.post()
    except Exception as e:
        logger.debug(f"Failed to post MCP tool run: {e}")

    try:
        result = await wrapped(*args, **kwargs)
        tool_run.end(outputs=result if result else {})
        try:
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to patch MCP tool run: {e}")
        return result
    except Exception as e:
        tool_run.end(error=str(e))
        try:
            tool_run.patch()
        except Exception:
            pass
        raise


# =============================================================================
# Manual tracing context (for advanced use cases)
# =============================================================================


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
