"""Client instrumentation for Claude Agent SDK."""

import logging
import time
from collections.abc import AsyncGenerator, AsyncIterable
from datetime import datetime, timezone
from functools import cache
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree, trace

from ._hooks import (
    _active_tool_runs,
    _transcript_traced_agents,
    clear_active_tool_runs,
    post_tool_use_failure_hook,
    post_tool_use_hook,
    pre_tool_use_hook,
    subagent_start_hook,
    subagent_stop_hook,
)
from ._messages import (
    build_llm_input,
    extract_usage_from_result_message,
    flatten_content_blocks,
)
from ._tools import (
    clear_current_llm_run,
    clear_parent_run_tree,
    get_parent_run_tree,
    set_current_llm_run,
    set_parent_run_tree,
)

logger = logging.getLogger(__name__)

TRACE_CHAIN_NAME = "claude.conversation"


@cache
def _get_package_version(package_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


LLM_RUN_NAME = "claude.assistant.turn"


class TurnLifecycle:
    """Track ongoing model runs so consecutive messages are recorded correctly.

    The Claude Agent SDK may deliver a single assistant turn as multiple
    ``AssistantMessage`` events (e.g. one with ``ThinkingBlock``, another
    with ``TextBlock``/``ToolUseBlock``).  Messages that share the same
    ``message_id`` are accumulated into a single LLM run.
    """

    def __init__(self, query_start_time: Optional[float] = None):
        self.current_run: Optional[Any] = None
        self.current_message_id: Optional[str] = None
        self.next_start_time: Optional[float] = query_start_time

    def start_llm_run(
        self,
        message: Any,
        prompt: Any,
        history: list[dict[str, Any]],
        parent: Optional[Any] = None,
    ) -> Optional[dict[str, Any]]:
        """Begin or continue a model run for *message*.

        If *message* has the same ``message_id`` as the current run the
        output is appended; otherwise a new run is started (ending any
        previous one first).
        """
        message_id = getattr(message, "message_id", None)
        start = self.next_start_time or time.time()

        # Same turn – just accumulate the output blocks.
        if message_id and message_id == self.current_message_id and self.current_run:
            content = flatten_content_blocks(getattr(message, "content", None))
            if content and self.current_run.outputs:
                prev = self.current_run.outputs.get("content", [])
                if isinstance(prev, list) and isinstance(content, list):
                    self.current_run.outputs["content"] = prev + content
                elif isinstance(content, list):
                    self.current_run.outputs["content"] = content
            return {"content": content, "role": "assistant"} if content else None

        # Different turn – close previous, open new.
        if self.current_run:
            self.current_run.end()
            self.current_run.patch()

        final_output, run = begin_llm_run_from_assistant_messages(
            [message], prompt, history, start_time=start, parent=parent
        )
        self.current_run = run
        self.current_message_id = message_id
        self.next_start_time = None

        # Expose the LLM run so tool hooks can nest under it
        if run:
            set_current_llm_run(run)

        return final_output

    def mark_next_start(self) -> None:
        """Mark when the next assistant message will start."""
        self.next_start_time = time.time()

    def add_usage(self, metrics: dict[str, Any]) -> None:
        """Attach usage from ``ResultMessage`` to the current (last) LLM run.

        The Python SDK's per-``AssistantMessage`` usage is unreliable
        (output tokens are under-counted), so we only set usage from the
        ``ResultMessage`` which has correct aggregated totals.  This means
        only the last LLM run in a conversation gets usage metadata.
        """
        if not (self.current_run and metrics):
            return
        meta = self.current_run.extra.setdefault("metadata", {})
        meta["usage_metadata"] = metrics

    def close(self) -> None:
        """End any open run gracefully."""
        if self.current_run:
            self.current_run.end()
            self.current_run.patch()
            self.current_run = None
        clear_current_llm_run()


def begin_llm_run_from_assistant_messages(
    messages: list[Any],
    prompt: Any,
    history: list[dict[str, Any]],
    start_time: Optional[float] = None,
    parent: Optional[Any] = None,
) -> tuple[Optional[dict[str, Any]], Optional[Any]]:
    """Create a traced model run from assistant messages."""
    if not messages or type(messages[-1]).__name__ != "AssistantMessage":
        return None, None

    last_msg = messages[-1]
    model = getattr(last_msg, "model", None)
    if parent is None:
        parent = get_parent_run_tree() or get_current_run_tree()
    if not parent:
        return None, None

    inputs = build_llm_input(prompt, history)
    outputs = [
        {"content": flatten_content_blocks(m.content), "role": "assistant"}
        for m in messages
        if hasattr(m, "content")
    ]

    llm_run = parent.create_child(
        name=LLM_RUN_NAME,
        run_type="llm",
        inputs={"messages": inputs} if inputs else {},
        extra={"metadata": {"ls_model_name": model}} if model else {},
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc)
        if start_time
        else None,
    )

    try:
        llm_run.post()
    except Exception as e:
        logger.warning(f"Failed to post LLM run: {e}")

    # Set outputs after posting so they are sent with end_time on the patch.
    llm_run.outputs = outputs[-1] if len(outputs) == 1 else {"content": outputs}

    final_content = (
        {"content": flatten_content_blocks(last_msg.content), "role": "assistant"}
        if hasattr(last_msg, "content")
        else None
    )
    return final_content, llm_run


def _inject_tracing_hooks(options: Any) -> None:
    """Inject LangSmith tracing hooks into ClaudeAgentOptions."""
    if not hasattr(options, "hooks"):
        return

    # Initialize hooks dict if not present
    if options.hooks is None:
        options.hooks = {}

    for event in (
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStart",
        "SubagentStop",
    ):
        if event not in options.hooks:
            options.hooks[event] = []

    try:
        from claude_agent_sdk import HookMatcher  # type: ignore[import-not-found]

        langsmith_pre_matcher = HookMatcher(matcher=None, hooks=[pre_tool_use_hook])
        langsmith_post_matcher = HookMatcher(matcher=None, hooks=[post_tool_use_hook])
        langsmith_failure_matcher = HookMatcher(
            matcher=None, hooks=[post_tool_use_failure_hook]
        )
        langsmith_subagent_start_matcher = HookMatcher(
            matcher=None, hooks=[subagent_start_hook]
        )
        langsmith_subagent_stop_matcher = HookMatcher(
            matcher=None, hooks=[subagent_stop_hook]
        )

        options.hooks["PreToolUse"].insert(0, langsmith_pre_matcher)
        options.hooks["PostToolUse"].insert(0, langsmith_post_matcher)
        options.hooks["PostToolUseFailure"].insert(0, langsmith_failure_matcher)
        options.hooks["SubagentStart"].insert(0, langsmith_subagent_start_matcher)
        options.hooks["SubagentStop"].insert(0, langsmith_subagent_stop_matcher)

        logger.debug("Injected LangSmith tracing hooks into ClaudeAgentOptions")
    except ImportError:
        logger.warning("Failed to import HookMatcher from claude_agent_sdk")
    except Exception as e:
        logger.warning(f"Failed to inject tracing hooks: {e}")


def _wrap_tool_handler(original_handler: Any) -> Any:
    """Wrap an MCP tool handler to propagate LangSmith run context.

    The Claude SDK runs hooks and tool handlers in different async task
    contexts, so contextvars set in ``PreToolUse`` are invisible to the
    handler.  This wrapper copies the active tool run into the contextvar
    before calling the original handler, so ``@traceable`` calls inside
    the handler nest correctly.
    """

    async def _wrapped(args: Any) -> Any:
        # The most recently added active tool run is the one
        # PreToolUse just created for this invocation.
        tool_run = _get_last_active_tool_run()
        if tool_run:
            from langsmith._internal import _context

            token = _context._PARENT_RUN_TREE.set(tool_run)
            try:
                return await original_handler(args)
            finally:
                _context._PARENT_RUN_TREE.reset(token)
        return await original_handler(args)

    return _wrapped


def _get_last_active_tool_run() -> Any:
    """Return the most recently created active tool run, or None."""
    if not _active_tool_runs:
        return None
    last_id = list(_active_tool_runs.keys())[-1]
    run, _ = _active_tool_runs[last_id]
    return run


def _unwrap_streamed_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Unwrap streaming input messages for trace display."""
    if not messages:
        return []

    formatted = []
    for msg in messages:
        if not isinstance(msg, dict):
            formatted.append(msg)
            continue

        if "message" in msg:
            inner = msg["message"]
            if isinstance(inner, dict):
                formatted.append(
                    {
                        "role": inner.get("role", "user"),
                        "content": inner.get("content", ""),
                    }
                )
            else:
                formatted.append(msg)
        else:
            formatted.append(msg)

    return formatted


def instrument_claude_client(original_class: Any) -> Any:
    """Wrap `ClaudeSDKClient` to trace both `query()` and `receive_response()`."""
    if getattr(original_class, "_langsmith_instrumented", False):
        return original_class  # Already wrapped, avoid double-tracing

    class TracedClaudeSDKClient(original_class):
        _langsmith_instrumented = True

        def __init__(self, *args: Any, **kwargs: Any):
            # Inject LangSmith tracing hooks into options before initialization
            options = kwargs.get("options") or (args[0] if args else None)
            if options:
                _inject_tracing_hooks(options)

            super().__init__(*args, **kwargs)
            self._prompt: Optional[str] = None
            self._start_time: Optional[float] = None
            self._streamed_input: Optional[list[dict[str, Any]]] = None

        async def query(self, *args: Any, **kwargs: Any) -> Any:
            """Capture prompt and start time, wrapping generators if needed."""
            self._start_time = time.time()
            self._streamed_input = None
            prompt = args[0] if args else kwargs.get("prompt")

            if prompt is None:
                pass
            elif isinstance(prompt, str):
                self._prompt = prompt
            elif isinstance(prompt, AsyncIterable):
                collector: list[dict[str, Any]] = []
                self._streamed_input = collector
                self._prompt = None

                async def _gen_wrapper() -> AsyncGenerator[dict[str, Any], None]:
                    async for msg in prompt:
                        collector.append(msg)
                        yield msg

                if args:
                    args = (_gen_wrapper(),) + args[1:]
                else:
                    kwargs["prompt"] = _gen_wrapper()
            else:
                self._prompt = str(prompt)

            return await super().query(*args, **kwargs)

        async def receive_response(self) -> AsyncGenerator[Any, None]:
            """Intercept message stream and record chain run activity."""
            messages = super().receive_response()

            # Capture configuration in inputs and metadata
            trace_inputs: dict[str, Any] = {}
            trace_metadata: dict[str, Any] = {
                "ls_integration": "claude-agent-sdk",
                "ls_integration_version": _get_package_version("claude_agent_sdk"),
            }

            # Track if we need to update input from captured streaming messages
            awaiting_streamed_input = self._streamed_input is not None

            # Add prompt to inputs (for string prompts)
            if self._prompt:
                trace_inputs["prompt"] = self._prompt

            # Add system_prompt to inputs if available
            if hasattr(self, "options") and self.options:
                if (
                    hasattr(self.options, "system_prompt")
                    and self.options.system_prompt
                ):
                    system_prompt = self.options.system_prompt
                    if isinstance(system_prompt, str):
                        trace_inputs["system"] = system_prompt
                    elif isinstance(system_prompt, dict):
                        # Handle SystemPromptPreset format
                        if system_prompt.get("type") == "preset":
                            preset_text = (
                                f"preset: {system_prompt.get('preset', 'claude_code')}"
                            )
                            if "append" in system_prompt:
                                preset_text += f"\nappend: {system_prompt['append']}"
                            trace_inputs["system"] = preset_text
                        else:
                            trace_inputs["system"] = system_prompt

                # Add other config to metadata
                for attr in ["model", "permission_mode", "max_turns"]:
                    if hasattr(self.options, attr):
                        val = getattr(self.options, attr)
                        if val is not None:
                            trace_metadata[attr] = val

            async with trace(
                name=TRACE_CHAIN_NAME,
                run_type="chain",
                inputs=trace_inputs,
                metadata={
                    **trace_metadata,
                    "ls_agent_type": "root",
                },
            ) as run:
                set_parent_run_tree(run)
                tracker = TurnLifecycle(self._start_time)
                collected: list[dict[str, Any]] = []

                prompt_for_llm: Any = self._prompt

                try:
                    async for msg in messages:
                        if awaiting_streamed_input and self._streamed_input:
                            unwrapped_messages = _unwrap_streamed_messages(
                                self._streamed_input
                            )
                            if unwrapped_messages:
                                run.inputs["messages"] = unwrapped_messages
                                prompt_for_llm = self._streamed_input
                            awaiting_streamed_input = False

                        msg_type = type(msg).__name__
                        if msg_type == "AssistantMessage":
                            # Skip messages from transcript-traced
                            # subagents — their LLM turns are traced
                            # from the JSONL transcript instead.
                            # Check both agent_id and parent_tool_use_id
                            # since SDK versions vary.
                            msg_agent_id = getattr(msg, "agent_id", None)
                            parent_tool_use_id = getattr(
                                msg, "parent_tool_use_id", None
                            )
                            is_subagent_msg = False
                            if (
                                msg_agent_id
                                and str(msg_agent_id) in _transcript_traced_agents
                            ):
                                is_subagent_msg = True
                            elif parent_tool_use_id:
                                is_subagent_msg = True

                            if is_subagent_msg:
                                yield msg
                                continue

                            content = tracker.start_llm_run(
                                msg,
                                prompt_for_llm,
                                collected,
                            )
                            if content:
                                collected.append(content)

                        elif msg_type == "UserMessage":
                            if hasattr(msg, "content"):
                                # Check if this is a tool result message
                                flattened = flatten_content_blocks(msg.content)
                                if (
                                    isinstance(flattened, list)
                                    and flattened
                                    and isinstance(flattened[0], dict)
                                    and flattened[0].get("type") == "tool_result"
                                ):
                                    # Format each tool result as a separate message
                                    for block in flattened:
                                        tool_use_id = block.get("tool_use_id")
                                        collected.append(
                                            {
                                                "role": "tool",
                                                "content": block.get("content", ""),
                                                "tool_call_id": tool_use_id,
                                            }
                                        )
                                        # Close orphaned tool runs whose
                                        # PostToolUse never fired (e.g.
                                        # permission-denied MCP tools).
                                        if (
                                            tool_use_id
                                            and tool_use_id in _active_tool_runs
                                        ):
                                            tool_run, _ = _active_tool_runs.pop(
                                                tool_use_id
                                            )
                                            result_content = block.get("content", "")
                                            is_error = block.get("is_error", False)
                                            tool_run.end(
                                                outputs={"output": result_content},
                                                error=str(result_content)
                                                if is_error
                                                else None,
                                            )
                                            try:
                                                tool_run.patch()
                                            except Exception as e:
                                                logger.warning(
                                                    "Failed to patch"
                                                    f" orphaned tool run: {e}"
                                                )
                                else:
                                    collected.append(
                                        {
                                            "content": flattened,
                                            "role": "user",
                                        }
                                    )
                            tracker.mark_next_start()
                        elif msg_type == "ResultMessage":
                            # Add usage metrics including cost
                            if hasattr(msg, "usage"):
                                usage = extract_usage_from_result_message(msg)
                                # Add total_cost to usage_metadata if available
                                if (
                                    hasattr(msg, "total_cost_usd")
                                    and msg.total_cost_usd is not None
                                ):
                                    usage["total_cost"] = msg.total_cost_usd
                                tracker.add_usage(usage)

                            # Add conversation-level metadata
                            meta = {
                                k: v
                                for k, v in {
                                    "num_turns": getattr(msg, "num_turns", None),
                                    "session_id": getattr(msg, "session_id", None),
                                    "duration_ms": getattr(msg, "duration_ms", None),
                                    "duration_api_ms": getattr(
                                        msg, "duration_api_ms", None
                                    ),
                                    "is_error": getattr(msg, "is_error", None),
                                }.items()
                                if v is not None
                            }
                            if meta:
                                run.metadata.update(meta)

                        yield msg
                    run.end(outputs=collected[-1] if collected else None)
                except Exception:
                    logger.exception("Error while tracing Claude Agent stream")
                finally:
                    tracker.close()
                    clear_parent_run_tree()
                    clear_active_tool_runs()

        async def __aenter__(self) -> "TracedClaudeSDKClient":
            await super().__aenter__()
            return self

        async def __aexit__(self, *args: Any) -> None:
            await super().__aexit__(*args)

    return TracedClaudeSDKClient
