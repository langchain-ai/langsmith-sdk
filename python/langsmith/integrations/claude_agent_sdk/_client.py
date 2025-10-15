"""Client instrumentation for Claude Agent SDK."""

import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Optional

from langsmith.run_helpers import get_current_run_tree, trace

from ._messages import (
    build_llm_input,
    extract_usage_from_result_message,
    flatten_content_blocks,
)
from ._tools import clear_parent_run_tree, set_parent_run_tree

logger = logging.getLogger(__name__)

TRACE_CHAIN_NAME = "claude.conversation"
LLM_RUN_NAME = "claude.assistant.turn"


class TurnLifecycle:
    """Track ongoing model runs so consecutive messages are recorded correctly."""

    def __init__(self, query_start_time: Optional[float] = None):
        self.current_run: Optional[Any] = None
        self.next_start_time: Optional[float] = query_start_time

    def start_llm_run(
        self, message: Any, prompt: Any, history: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Begin a new model run, ending any existing one."""
        start = self.next_start_time or time.time()

        if self.current_run:
            self.current_run.end()
            self.current_run.patch()

        final_output, run = begin_llm_run_from_assistant_messages(
            [message], prompt, history, start_time=start
        )
        self.current_run = run
        self.next_start_time = None
        return final_output

    def mark_next_start(self) -> None:
        """Mark when the next assistant message will start."""
        self.next_start_time = time.time()

    def add_usage(self, metrics: dict[str, Any]) -> None:
        """Attach token usage details to the current run."""
        if not (self.current_run and metrics):
            return
        meta = self.current_run.extra.setdefault("metadata", {}).setdefault(
            "usage_metadata", {}
        )
        meta.update(metrics)
        try:
            self.current_run.patch()
        except Exception as e:
            logger.warning(f"Failed to update usage metrics: {e}")

    def close(self) -> None:
        """End any open run gracefully."""
        if self.current_run:
            self.current_run.end()
            self.current_run.patch()
            self.current_run = None


def begin_llm_run_from_assistant_messages(
    messages: list[Any],
    prompt: Any,
    history: list[dict[str, Any]],
    start_time: Optional[float] = None,
) -> tuple[Optional[dict[str, Any]], Optional[Any]]:
    """Create a traced model run from assistant messages."""
    if not messages or type(messages[-1]).__name__ != "AssistantMessage":
        return None, None

    last_msg = messages[-1]
    model = getattr(last_msg, "model", None)
    parent = get_current_run_tree()
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
        inputs=inputs if len(inputs) > 1 else inputs[0] if inputs else {},  # type: ignore[arg-type]
        outputs=outputs[-1] if len(outputs) == 1 else {"content": outputs},
        extra={"metadata": {"ls_model_name": model}} if model else {},
        start_time=datetime.fromtimestamp(start_time, tz=timezone.utc)
        if start_time
        else None,
    )

    try:
        llm_run.post()
    except Exception as e:
        logger.warning(f"Failed to post LLM run: {e}")

    final_content = (
        {"content": flatten_content_blocks(last_msg.content), "role": "assistant"}
        if hasattr(last_msg, "content")
        else None
    )
    return final_content, llm_run


def instrument_claude_client(original_class: Any) -> Any:
    """Wrap ClaudeSDKClient to trace both query() and receive_response()."""

    class TracedClaudeSDKClient(original_class):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, **kwargs)
            self._prompt: Optional[str] = None
            self._start_time: Optional[float] = None

        async def query(self, *args: Any, **kwargs: Any) -> Any:
            """Capture prompt and timestamp when query starts."""
            self._start_time = time.time()
            self._prompt = str(kwargs.get("prompt") or (args[0] if args else ""))
            return await super().query(*args, **kwargs)

        async def receive_response(self) -> AsyncGenerator[Any, None]:
            """Intercept message stream and record chain run activity."""
            messages = super().receive_response()

            # Capture configuration in inputs and metadata
            trace_inputs: dict[str, Any] = {}
            trace_metadata = {}

            # Add prompt to inputs
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
                metadata=trace_metadata,
            ) as run:
                set_parent_run_tree(run)
                tracker = TurnLifecycle(self._start_time)
                collected: list[dict[str, Any]] = []

                try:
                    async for msg in messages:
                        msg_type = type(msg).__name__
                        if msg_type == "AssistantMessage":
                            content = tracker.start_llm_run(
                                msg, self._prompt, collected
                            )
                            if content:
                                collected.append(content)
                        elif msg_type == "UserMessage":
                            if hasattr(msg, "content"):
                                collected.append(
                                    {
                                        "content": flatten_content_blocks(msg.content),
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

        async def __aenter__(self) -> "TracedClaudeSDKClient":
            await super().__aenter__()
            return self

        async def __aexit__(self, *args: Any) -> None:
            await super().__aexit__(*args)

    return TracedClaudeSDKClient
