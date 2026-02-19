"""Client instrumentation for Google ADK using wrapt."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import datetime, timezone
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree, set_tracing_parent, trace

from ._config import get_tracing_config
from ._messages import convert_llm_request_to_messages, has_function_calls
from ._usage import extract_model_name, extract_usage_from_response

_LS_PROVIDER_VERTEXAI = "google_vertexai"
_LS_PROVIDER_GOOGLE_AI = "google_ai"


def extract_tools_from_llm_request(llm_request: Any) -> list[dict[str, Any]]:
    """Extract tool definitions from LlmRequest and convert to OpenAI format."""
    config = getattr(llm_request, "config", None)
    if not config:
        return []

    tools_list = getattr(config, "tools", None)
    if not tools_list:
        return []

    result = []
    for tool in tools_list:
        for func_decl in getattr(tool, "function_declarations", None) or []:
            try:
                dumped = func_decl.model_dump(exclude_none=True)
                result.append(
                    {
                        "type": "function",
                        "function": dumped,
                    }
                )
            except Exception:
                pass

    return result


def _get_ls_provider() -> str:
    """Detect provider based on GOOGLE_GENAI_USE_VERTEXAI env var."""
    import os

    use_vertexai = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    return _LS_PROVIDER_VERTEXAI if use_vertexai else _LS_PROVIDER_GOOGLE_AI


logger = logging.getLogger(__name__)

TRACE_CHAIN_NAME = "google_adk.session"

# Attribute name used to bridge the root run from Runner.run (sync) into the
# background thread where Runner.run_async executes. Runner.run spins up a
# new thread for its internal asyncio event loop, so context vars don't
# propagate automatically. Storing the run on the instance (a plain object
# attribute) crosses the thread boundary, and wrap_runner_run_async picks it
# up and re-establishes it as a context var.
_SYNC_ROOT_RUN_ATTR = "_langsmith_root_run"


def _extract_text_from_content(content: Any) -> Optional[str]:
    if content is None:
        return None
    parts = getattr(content, "parts", None)
    if not parts:
        return None
    text_parts = [str(p.text) for p in parts if getattr(p, "text", None)]
    return " ".join(text_parts) if text_parts else None


def _iter_invocation_events(ctx: Any) -> list[Any]:
    """Get session events for the current invocation."""
    session = getattr(ctx, "session", None)
    if session is None:
        return []
    invocation_id = getattr(ctx, "invocation_id", None)
    events = getattr(session, "events", None) or []
    if invocation_id is None:
        return list(events)
    return [e for e in events if getattr(e, "invocation_id", None) == invocation_id]


def _extract_latest_invocation_text(ctx: Any) -> Optional[str]:
    """Get the latest text from session events for the current invocation."""
    for event in reversed(_iter_invocation_events(ctx)):
        text = _extract_text_from_content(getattr(event, "content", None))
        if text:
            return text
    return None


def wrap_runner_run(wrapped: Any, instance: Any, args: Any, kwargs: Any) -> Any:
    """Wrap Runner.run to create a root trace for synchronous execution.

    Runner.run internally starts a new thread to run its async event loop, so
    context vars set here would not be visible to code running in that thread.
    We bridge the gap by storing the root run on the instance (a plain object
    attribute that IS visible across threads) so that wrap_runner_run_async can
    re-establish it as a context var inside the async event loop.
    """
    config = get_tracing_config()
    trace_name = config.get("name") or TRACE_CHAIN_NAME

    trace_inputs: dict[str, Any] = {}
    if new_message := kwargs.get("new_message"):
        if text := _extract_text_from_content(new_message):
            trace_inputs["input"] = text

    trace_metadata: dict[str, Any] = {
        "ls_provider": _get_ls_provider(),
        **(config.get("metadata") or {}),
    }
    if app_name := getattr(instance, "app_name", None):
        trace_metadata["app_name"] = app_name
    if user_id := kwargs.get("user_id"):
        trace_metadata["user_id"] = user_id
    if session_id := kwargs.get("session_id"):
        trace_metadata["session_id"] = session_id

    def _trace_run():
        with trace(
            name=trace_name,
            run_type="chain",
            inputs=trace_inputs,
            project_name=config.get("project_name"),
            tags=config.get("tags"),
            metadata=trace_metadata,
        ) as root_run:
            setattr(instance, _SYNC_ROOT_RUN_ATTR, root_run)
            try:
                events = list(wrapped(*args, **kwargs))
                final_output = None
                for event in reversed(events):
                    if content := getattr(event, "content", None):
                        if text := _extract_text_from_content(content):
                            final_output = text
                            break
                root_run.end(outputs={"output": final_output} if final_output else None)
                yield from events
            except Exception as e:
                root_run.end(error=str(e))
                raise
            finally:
                setattr(instance, _SYNC_ROOT_RUN_ATTR, None)

    return _trace_run()


async def wrap_runner_run_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrap Runner.run_async to create a root trace for asynchronous execution.

    When called from the background thread spawned by Runner.run, the root run
    stored on the instance is re-established as a context var so that
    wrap_agent_run_async and wrap_flow_call_llm_async can find the parent via
    get_current_run_tree().
    """
    root_run = getattr(instance, _SYNC_ROOT_RUN_ATTR, None)
    if root_run is not None:
        # sync bridge: re-establish root run as context var in this thread
        with set_tracing_parent(root_run):
            async with aclosing(wrapped(*args, **kwargs)) as agen:
                async for event in agen:
                    yield event
        return

    config = get_tracing_config()
    trace_name = config.get("name") or TRACE_CHAIN_NAME

    trace_inputs: dict[str, Any] = {}
    if new_message := kwargs.get("new_message"):
        if text := _extract_text_from_content(new_message):
            trace_inputs["input"] = text

    trace_metadata: dict[str, Any] = {
        "ls_provider": _get_ls_provider(),
        **(config.get("metadata") or {}),
    }
    if app_name := getattr(instance, "app_name", None):
        trace_metadata["app_name"] = app_name
    if user_id := kwargs.get("user_id"):
        trace_metadata["user_id"] = user_id
    if session_id := kwargs.get("session_id"):
        trace_metadata["session_id"] = session_id

    async def _trace_run_async() -> AsyncGenerator[Any, None]:
        async with trace(
            name=trace_name,
            run_type="chain",
            inputs=trace_inputs,
            project_name=config.get("project_name"),
            tags=config.get("tags"),
            metadata=trace_metadata,
        ) as run:
            try:
                final_output: Optional[str] = None
                async with aclosing(wrapped(*args, **kwargs)) as agen:
                    async for event in agen:
                        if content := getattr(event, "content", None):
                            if text := _extract_text_from_content(content):
                                final_output = text
                        yield event
                run.end(outputs={"output": final_output} if final_output else None)
            except Exception as e:
                run.end(error=str(e))
                raise

    async for event in _trace_run_async():
        yield event


async def wrap_agent_run_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrap BaseAgent.run_async to create a chain span for each agent invocation."""
    parent = get_current_run_tree()
    if not parent:
        async with aclosing(wrapped(*args, **kwargs)) as agen:
            async for event in agen:
                yield event
        return

    ctx = args[0] if args else kwargs.get("parent_context")
    agent_name = getattr(instance, "name", None) or type(instance).__name__

    inputs: dict[str, Any] = {}
    if ctx is not None:
        if latest := _extract_latest_invocation_text(ctx):
            inputs["input"] = latest

    async with trace(name=agent_name, run_type="chain", inputs=inputs) as agent_run:
        try:
            final_output: Optional[str] = None
            async with aclosing(wrapped(*args, **kwargs)) as agen:
                async for event in agen:
                    if content := getattr(event, "content", None):
                        if text := _extract_text_from_content(content):
                            final_output = text
                    yield event
            agent_run.end(outputs={"output": final_output} if final_output else None)
        except Exception as e:
            agent_run.end(error=str(e))
            raise


async def wrap_tool_run_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrap BaseTool.run_async (all tool subclasses) to trace tool invocations."""
    parent = get_current_run_tree()
    if not parent:
        return await wrapped(*args, **kwargs)

    tool_name = getattr(instance, "name", None) or type(instance).__name__
    tool_args = kwargs.get("args") or (args[0] if args else {})
    inputs = tool_args if isinstance(tool_args, dict) else {"args": tool_args}

    start_time = time.time()
    tool_run = parent.create_child(
        name=tool_name,
        run_type="tool",
        inputs=inputs,
        extra={"metadata": {"ls_provider": _get_ls_provider()}},
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
    )

    try:
        tool_run.post()
    except Exception as e:
        logger.debug(f"Failed to post tool run: {e}")

    try:
        result = await wrapped(*args, **kwargs)
        if isinstance(result, dict):
            outputs = result
        elif isinstance(result, list):
            outputs = {"content": result}
        elif result is not None:
            outputs = {"output": str(result)}
        else:
            outputs = {}
        tool_run.end(outputs=outputs)
        try:
            tool_run.patch()
        except Exception as e:
            logger.debug(f"Failed to patch tool run: {e}")
        return result
    except Exception as e:
        tool_run.end(error=str(e))
        try:
            tool_run.patch()
        except Exception as patch_e:
            logger.debug(f"Failed to patch tool run on error: {patch_e}")
        raise


def _determine_llm_call_type(llm_request: Any, llm_response: Any) -> str:
    try:
        for content in getattr(llm_request, "contents", None) or []:
            for part in getattr(content, "parts", None) or []:
                if hasattr(part, "function_response") and part.function_response:
                    return "response_generation"
        if has_function_calls(llm_response):
            return "tool_selection"
        return "direct_response"
    except Exception:
        return "unknown"


async def wrap_flow_call_llm_async(
    wrapped: Any, instance: Any, args: Any, kwargs: Any
) -> Any:
    """Wrap BaseLlmFlow._call_llm_async to capture LLM calls with TTFT tracking."""
    parent = get_current_run_tree()
    if not parent:
        async for event in wrapped(*args, **kwargs):
            yield event
        return

    llm_request = args[1] if len(args) > 1 else kwargs.get("llm_request")
    model_name = extract_model_name(llm_request) if llm_request else None
    messages = convert_llm_request_to_messages(llm_request) if llm_request else None
    tools = extract_tools_from_llm_request(llm_request) if llm_request else []

    inputs: dict[str, Any] = {}
    if messages:
        inputs["messages"] = messages

    metadata: dict[str, Any] = {"ls_provider": _get_ls_provider()}
    if model_name:
        metadata["ls_model_name"] = model_name

    # Build extra dict with invocation_params if tools exist
    extra: dict[str, Any] = {"metadata": metadata}
    if tools:
        extra["invocation_params"] = {"tools": tools}

    start_time = time.time()
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
        logger.debug(f"Failed to post LLM run: {e}")

    first_token_time: Optional[float] = None
    last_event = None
    event_with_content = None

    try:
        async with aclosing(wrapped(*args, **kwargs)) as agen:
            async for event in agen:
                is_partial = getattr(event, "partial", False)

                if first_token_time is None and is_partial:
                    first_token_time = time.time()
                    try:
                        llm_run.add_event(
                            {
                                "name": "new_token",
                                "time": datetime.fromtimestamp(
                                    first_token_time, tz=timezone.utc
                                ).isoformat(),
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Failed to add new_token event: {e}")

                last_event = event
                if hasattr(event, "content") and event.content is not None:
                    event_with_content = event
                yield event

        outputs: dict[str, Any] = {"role": "assistant"}
        content_source = event_with_content or last_event

        if (
            content_source
            and hasattr(content_source, "content")
            and content_source.content
        ):
            parts = getattr(content_source.content, "parts", None) or []
            text_parts, tool_calls = [], []

            for i, part in enumerate(parts):
                if hasattr(part, "text") and part.text:
                    text_parts.append(str(part.text))
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": getattr(fc, "name", ""),
                                "arguments": json.dumps(
                                    dict(fc.args) if getattr(fc, "args", None) else {}
                                ),
                            },
                        }
                    )

            outputs["content"] = " ".join(text_parts) if text_parts else None
            if tool_calls:
                outputs["tool_calls"] = tool_calls

        if last_event:
            if usage := extract_usage_from_response(last_event):
                llm_run.extra.setdefault("metadata", {})["usage_metadata"] = usage

        if first_token_time is not None:
            llm_run.extra.setdefault("metadata", {})["time_to_first_token"] = (
                first_token_time - start_time
            )

        if last_event and llm_request:
            llm_run.extra.setdefault("metadata", {})["llm_call_type"] = (
                _determine_llm_call_type(llm_request, last_event)
            )

        llm_run.end(outputs=outputs)
        try:
            llm_run.patch()
        except Exception as e:
            logger.debug(f"Failed to patch LLM run: {e}")

    except Exception as e:
        llm_run.end(error=str(e))
        try:
            llm_run.patch()
        except Exception as patch_e:
            logger.debug(f"Failed to patch LLM run on error: {patch_e}")
        raise


def create_traced_session_context(
    name: Optional[str] = None,
    project_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    inputs: Optional[dict[str, Any]] = None,
):
    """Create a trace context for manual session tracing."""
    config = get_tracing_config()
    return trace(
        name=name or config.get("name") or TRACE_CHAIN_NAME,
        run_type="chain",
        inputs=inputs or {},
        project_name=project_name or config.get("project_name"),
        tags=tags or config.get("tags"),
        metadata={**(config.get("metadata") or {}), **(metadata or {})},
    )
