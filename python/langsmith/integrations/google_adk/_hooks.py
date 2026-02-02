"""Callback-based tracing for Google ADK.

This module provides callback handlers that trace agent, model, and tool
invocations by implementing Google ADK's callback interface.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from langsmith.run_helpers import get_current_run_tree
from langsmith.run_trees import RunTree

from ._messages import (
    convert_adk_content_to_langsmith,
    convert_llm_request_to_messages,
    has_function_calls,
    has_function_response_in_request,
)
from ._tools import get_parent_run_tree
from ._usage import extract_model_name, extract_usage_from_response

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Enable debug logging for development
# logging.basicConfig(level=logging.DEBUG)

DEBUG_TRACE_DATA = False  # Set to True to log trace inputs/outputs

# Storage for correlating before/after callbacks
# Key: invocation_id, Value: (run_tree, start_time, optional first_token_time)
_active_agent_runs: dict[str, tuple[RunTree, float]] = {}
_active_llm_runs: dict[str, tuple[RunTree, float, float | None]] = {}
_active_tool_runs: dict[str, tuple[RunTree, float]] = {}


def _get_invocation_id(callback_context: Any) -> str | None:
    """Extract invocation ID from callback context.

    Args:
        callback_context: The ADK CallbackContext object.

    Returns:
        The invocation ID or None if not available.
    """
    return getattr(callback_context, "invocation_id", None)


def _get_agent_name(callback_context: Any) -> str:
    """Extract agent name from callback context.

    Args:
        callback_context: The ADK CallbackContext object.

    Returns:
        The agent name or a default value.
    """
    agent_name = getattr(callback_context, "agent_name", None)
    if agent_name:
        return str(agent_name)

    # Try to get from the agent attribute
    agent = getattr(callback_context, "agent", None)
    if agent:
        name = getattr(agent, "name", None)
        if name:
            return str(name)

    return "google_adk_agent"


def _get_parent_run() -> RunTree | None:
    """Get the parent run tree from thread-local or context.

    Returns:
        The parent RunTree or None.
    """
    return get_parent_run_tree() or get_current_run_tree()


def _determine_llm_call_type(llm_request: Any, llm_response: Any) -> str:
    """Classify LLM call based on request/response content.

    Args:
        llm_request: The LlmRequest object.
        llm_response: The LlmResponse object.

    Returns:
        One of: "tool_selection", "response_generation", "direct_response"
    """
    # Check if this is a response after tool execution
    if has_function_response_in_request(llm_request):
        return "response_generation"

    # Check if the model is selecting tools
    if has_function_calls(llm_response):
        return "tool_selection"

    # Default: direct response without tools
    return "direct_response"


def before_agent_callback(
    callback_context: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Create chain run for agent invocation.

    This callback is invoked before an agent starts processing.

    Args:
        callback_context: ADK CallbackContext with invocation details.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    invocation_id = _get_invocation_id(callback_context)
    if not invocation_id:
        logger.debug("before_agent_callback called without invocation_id, skipping")
        return

    agent_name = _get_agent_name(callback_context)

    try:
        parent = _get_parent_run()
        if not parent:
            logger.debug(f"No parent run tree found for agent {agent_name}")
            return

        if DEBUG_TRACE_DATA:
            logger.debug(
                f"Agent parent run: name={parent.name}, "
                f"trace_id={parent.trace_id}, run_id={parent.id}"
            )

        start_time = time.time()

        # Extract user content from callback context if available
        # Use flat text format, not nested parts
        user_content = getattr(callback_context, "user_content", None)
        inputs: dict[str, Any] = {}
        if user_content:
            # Extract text from content parts
            parts = getattr(user_content, "parts", None)
            if parts:
                text_parts = []
                for part in parts:
                    text = getattr(part, "text", None)
                    if text:
                        text_parts.append(str(text))
                if text_parts:
                    inputs["input"] = " ".join(text_parts)

        if DEBUG_TRACE_DATA:
            logger.debug(f"Agent span inputs: {json.dumps(inputs, indent=2)}")

        agent_run = parent.create_child(
            name=agent_name,
            run_type="chain",
            inputs=inputs,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )

        try:
            agent_run.post()
        except Exception as e:
            logger.warning(f"Failed to post agent run for {agent_name}: {e}")

        _active_agent_runs[invocation_id] = (agent_run, start_time)
        logger.debug(f"Started agent trace for {agent_name} (id={invocation_id})")

    except Exception as e:
        logger.warning(
            f"Error in before_agent_callback for {agent_name}: {e}", exc_info=True
        )


def after_agent_callback(
    callback_context: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """End agent run with final output.

    This callback is invoked after an agent finishes processing.

    Args:
        callback_context: ADK CallbackContext with invocation details.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    invocation_id = _get_invocation_id(callback_context)
    if not invocation_id:
        logger.debug("after_agent_callback called without invocation_id, skipping")
        return

    agent_name = _get_agent_name(callback_context)

    try:
        run_info = _active_agent_runs.pop(invocation_id, None)
        if not run_info:
            logger.debug(
                f"No matching before_agent_callback for {agent_name} "
                f"(id={invocation_id})"
            )
            return

        agent_run, start_time = run_info

        # Extract final output if available
        outputs: dict[str, Any] = {}
        final_response = getattr(callback_context, "final_response", None)
        if final_response:
            outputs["output"] = convert_adk_content_to_langsmith(final_response)

        agent_run.end(outputs=outputs if outputs else None)

        try:
            agent_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch agent run for {agent_name}: {e}")

        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            f"Completed agent trace for {agent_name} "
            f"(id={invocation_id}, duration={duration_ms:.2f}ms)"
        )

    except Exception as e:
        logger.warning(
            f"Error in after_agent_callback for {agent_name}: {e}", exc_info=True
        )


def before_model_callback(
    callback_context: Any,
    llm_request: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Create LLM run before model call.

    This callback is invoked before the model is called.

    Args:
        callback_context: ADK CallbackContext with invocation details.
        llm_request: The LlmRequest being sent to the model.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    invocation_id = _get_invocation_id(callback_context)
    if not invocation_id:
        logger.debug("before_model_callback called without invocation_id, skipping")
        return

    try:
        parent = _get_parent_run()
        if not parent:
            logger.debug("No parent run tree found for LLM call")
            return

        start_time = time.time()

        # Extract model name and messages
        model_name = extract_model_name(llm_request)
        messages = convert_llm_request_to_messages(llm_request)

        # Build inputs
        inputs: dict[str, Any] = {}
        if messages:
            inputs["messages"] = messages

        if DEBUG_TRACE_DATA:
            logger.debug(f"LLM input messages: {json.dumps(messages, indent=2)}")

        # Build extra metadata
        extra: dict[str, Any] = {}
        if model_name:
            extra["metadata"] = {"ls_model_name": model_name}

        llm_run = parent.create_child(
            name=model_name or "google_adk_llm",
            run_type="llm",
            inputs=inputs,
            extra=extra,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )

        try:
            llm_run.post()
        except Exception as e:
            logger.warning(f"Failed to post LLM run: {e}")

        # Store with None for first_token_time (to be set on first partial response)
        _active_llm_runs[invocation_id] = (llm_run, start_time, None)
        logger.debug(f"Started LLM trace (id={invocation_id})")

    except Exception as e:
        logger.warning(f"Error in before_model_callback: {e}", exc_info=True)


def after_model_callback(
    callback_context: Any,
    llm_response: Any,
    *args: Any,
    **kwargs: Any,
) -> None:
    """End LLM run with response and usage.

    This callback is invoked after the model responds.

    Args:
        callback_context: ADK CallbackContext with invocation details.
        llm_response: The LlmResponse from the model.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    invocation_id = _get_invocation_id(callback_context)
    if not invocation_id:
        logger.debug("after_model_callback called without invocation_id, skipping")
        return

    try:
        run_info = _active_llm_runs.get(invocation_id)
        if not run_info:
            logger.debug(f"No matching before_model_callback (id={invocation_id})")
            return

        llm_run, start_time, first_token_time = run_info

        # Check if this is a partial/streaming response
        is_partial = getattr(llm_response, "partial", False)

        if DEBUG_TRACE_DATA:
            logger.debug(
                f"LLM response partial={is_partial}, "
                f"raw partial attr={getattr(llm_response, 'partial', 'N/A')}"
            )

        if is_partial:
            # Track TTFT on first partial response
            if first_token_time is None:
                current_time = time.time()
                _active_llm_runs[invocation_id] = (llm_run, start_time, current_time)

                # Emit new_token event for TTFT tracking
                try:
                    llm_run.add_event(
                        name="new_token",
                        time=datetime.fromtimestamp(current_time, tz=timezone.utc),
                    )
                except Exception as e:
                    logger.debug(f"Failed to add new_token event: {e}")
            return  # Don't finalize yet for partial responses

        # Final response - remove from active runs and finalize
        _active_llm_runs.pop(invocation_id, None)

        # Build OpenAI-compatible output format
        outputs: dict[str, Any] = {"role": "assistant"}

        # Extract response content
        content = getattr(llm_response, "content", None)
        if content:
            content_parts = convert_adk_content_to_langsmith(content)

            # Separate text content from tool calls
            text_parts = []
            tool_calls = []
            tool_call_index = 0

            for part in content_parts:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "tool_use":
                    # Format as OpenAI-compatible tool_call
                    tool_calls.append({
                        "id": f"call_{tool_call_index}",
                        "type": "function",
                        "function": {
                            "name": part.get("name", ""),
                            "arguments": json.dumps(part.get("input", {})),
                        },
                    })
                    tool_call_index += 1

            # Set content - join text parts or None if only tool calls
            if text_parts:
                outputs["content"] = " ".join(text_parts)
            else:
                outputs["content"] = None

            # Add tool_calls if present
            if tool_calls:
                outputs["tool_calls"] = tool_calls

        # Extract finish reason
        finish_reason = getattr(llm_response, "finish_reason", None)
        if finish_reason:
            outputs["finish_reason"] = str(finish_reason)

        # Extract usage metrics
        usage = extract_usage_from_response(llm_response)
        if usage:
            llm_run.extra.setdefault("metadata", {})["usage_metadata"] = usage

        if DEBUG_TRACE_DATA:
            logger.debug(f"LLM output: {json.dumps(outputs, indent=2)}")

        llm_run.end(outputs=outputs)

        try:
            llm_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch LLM run: {e}")

        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            f"Completed LLM trace (id={invocation_id}, duration={duration_ms:.2f}ms)"
        )

    except Exception as e:
        logger.warning(f"Error in after_model_callback: {e}", exc_info=True)


def before_tool_callback(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
    *other_args: Any,
    **kwargs: Any,
) -> None:
    """Create tool run before execution.

    This callback is invoked before a tool is executed.

    Args:
        tool: The BaseTool being executed.
        args: The arguments passed to the tool.
        tool_context: The ToolContext with execution details.
        *other_args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    # Get function_call_id for correlation
    function_call_id = getattr(tool_context, "function_call_id", None)
    if not function_call_id:
        # Try to generate a unique ID
        function_call_id = f"tool_{id(tool)}_{time.time()}"

    tool_name = getattr(tool, "name", None) or type(tool).__name__

    try:
        parent = _get_parent_run()
        if not parent:
            logger.debug(f"No parent run tree found for tool {tool_name}")
            return

        start_time = time.time()

        tool_run = parent.create_child(
            name=tool_name,
            run_type="tool",
            inputs=args if args else {},
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )

        try:
            tool_run.post()
        except Exception as e:
            logger.warning(f"Failed to post tool run for {tool_name}: {e}")

        _active_tool_runs[function_call_id] = (tool_run, start_time)
        logger.debug(f"Started tool trace for {tool_name} (id={function_call_id})")

    except Exception as e:
        logger.warning(
            f"Error in before_tool_callback for {tool_name}: {e}", exc_info=True
        )


def after_tool_callback(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
    tool_response: Any,
    *other_args: Any,
    **kwargs: Any,
) -> None:
    """End tool run with response.

    This callback is invoked after a tool finishes execution.

    Args:
        tool: The BaseTool that was executed.
        args: The arguments that were passed to the tool.
        tool_context: The ToolContext with execution details.
        tool_response: The response from the tool.
        *other_args: Additional positional arguments.
        **kwargs: Additional keyword arguments.
    """
    # Get function_call_id for correlation
    function_call_id = getattr(tool_context, "function_call_id", None)
    if not function_call_id:
        # Try the same ID generation as before_tool_callback
        function_call_id = f"tool_{id(tool)}_{time.time()}"

    tool_name = getattr(tool, "name", None) or type(tool).__name__

    try:
        run_info = _active_tool_runs.pop(function_call_id, None)
        if not run_info:
            logger.debug(
                f"No matching before_tool_callback for {tool_name} "
                f"(id={function_call_id})"
            )
            return

        tool_run, start_time = run_info

        # Format output
        if isinstance(tool_response, dict):
            outputs = tool_response
        elif isinstance(tool_response, list):
            outputs = {"content": tool_response}
        elif tool_response is not None:
            outputs = {"output": str(tool_response)}
        else:
            outputs = {}

        # Check for errors
        is_error = False
        error_msg = None
        if isinstance(tool_response, dict):
            is_error = tool_response.get("is_error", False)
            if is_error:
                error_msg = tool_response.get("error") or tool_response.get("output")

        tool_run.end(
            outputs=outputs,
            error=str(error_msg) if error_msg else None,
        )

        try:
            tool_run.patch()
        except Exception as e:
            logger.warning(f"Failed to patch tool run for {tool_name}: {e}")

        duration_ms = (time.time() - start_time) * 1000
        logger.debug(
            f"Completed tool trace for {tool_name} "
            f"(id={function_call_id}, duration={duration_ms:.2f}ms)"
        )

    except Exception as e:
        logger.warning(
            f"Error in after_tool_callback for {tool_name}: {e}", exc_info=True
        )


def clear_active_runs() -> None:
    """Clear all active runs.

    This should be called when a session ends to avoid memory leaks
    and to clean up any orphaned runs.
    """
    global _active_agent_runs, _active_llm_runs, _active_tool_runs

    # End orphaned agent runs
    for invocation_id, (run, _) in _active_agent_runs.items():
        try:
            run.end(error="Agent run not completed (session ended)")
            run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned agent run {invocation_id}: {e}")

    # End orphaned LLM runs
    for invocation_id, (run, _, _) in _active_llm_runs.items():
        try:
            run.end(error="LLM run not completed (session ended)")
            run.patch()
        except Exception as e:
            logger.debug(f"Failed to clean up orphaned LLM run {invocation_id}: {e}")

    # End orphaned tool runs
    for function_call_id, (run, _) in _active_tool_runs.items():
        try:
            run.end(error="Tool run not completed (session ended)")
            run.patch()
        except Exception as e:
            logger.debug(
                f"Failed to clean up orphaned tool run {function_call_id}: {e}"
            )

    _active_agent_runs.clear()
    _active_llm_runs.clear()
    _active_tool_runs.clear()
