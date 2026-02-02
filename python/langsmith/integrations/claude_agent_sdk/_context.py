"""Stream context management for Claude Agent SDK tracing."""

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from ._messages import (
    convert_from_anthropic_message,
    extract_usage_from_assistant_message,
    is_task_tool,
    is_tool_block,
)
from ._usage import aggregate_usage_from_model_usage, correct_usage_from_results

if TYPE_CHECKING:
    from langsmith.run_trees import RunTree

logger = logging.getLogger(__name__)


class StreamManager:
    """Manages message accumulation and run tree creation for Claude Agent SDK.

    This class replaces TurnLifecycle with a JS-aligned approach that:
    - Accumulates outputs to the same run using message keys
    - Tracks tools by tool_use_id
    - Creates proper parent-child relationships for subagents
    """

    def __init__(self, root_run: "RunTree"):
        """Initialize StreamManager with the root run tree.

        Args:
            root_run: The root RunTree for the conversation
        """
        self.namespaces: dict[str, RunTree] = {"root": root_run}
        self.history: dict[str, list[Any]] = {"root": []}

        # Assistant runs keyed by {namespace}:{model}:{sequence}
        self.assistant_runs: dict[str, RunTree] = {}

        # Tool runs keyed by tool_use_id
        self.tools: dict[str, RunTree] = {}

        # Sequence counters for generating run keys (workaround for missing message ID)
        self._sequence_counters: dict[str, int] = {}

        # Track all run trees for cleanup
        self._run_trees: list[RunTree] = []

        # Track tool_use_ids managed by this StreamManager
        self._managed_tool_ids: set[str] = set()

    def _get_run_key(self, msg: Any, namespace: str) -> str:
        """Generate a unique key for an assistant run.

        Since Python SDK AssistantMessage doesn't have an 'id' field like JS,
        we key by namespace:model:sequence instead.
        """
        model = getattr(msg.message, "model", None) if hasattr(msg, "message") else None
        model = model or "unknown"
        key_base = f"{namespace}:{model}"
        self._sequence_counters.setdefault(key_base, 0)
        self._sequence_counters[key_base] += 1
        return f"{key_base}:{self._sequence_counters[key_base]}"

    def _create_child(
        self,
        namespace: str,
        name: str,
        run_type: str,
        inputs: dict[str, Any],
        start_time: float,
        outputs: Optional[dict[str, Any]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> "RunTree":
        """Create a child run under the specified namespace."""
        parent = self.namespaces.get(namespace)
        if not parent:
            parent = self.namespaces["root"]

        run_tree = parent.create_child(
            name=name,
            run_type=run_type,
            inputs=inputs,
            outputs=outputs,
            extra=extra,
            start_time=datetime.fromtimestamp(start_time, tz=timezone.utc),
        )

        try:
            run_tree.post()
        except Exception as e:
            logger.warning(f"Failed to post run {name}: {e}")

        self._run_trees.append(run_tree)
        return run_tree

    def add_message(self, msg: Any, event_time: Optional[float] = None) -> None:
        """Process and add a message to the stream.

        Args:
            msg: SDK message (AssistantMessage, UserMessage, ResultMessage)
            event_time: Time the message was received
        """
        if event_time is None:
            event_time = time.time()

        # Short-circuit if no root run
        if "root" not in self.namespaces:
            return

        msg_type = type(msg).__name__

        if msg_type == "ResultMessage":
            self._handle_result_message(msg)
            return

        # Skip non-user/non-assistant messages
        if msg_type not in ("AssistantMessage", "UserMessage"):
            return

        # Determine namespace from parent_tool_use_id
        parent_tool_use_id = getattr(msg, "parent_tool_use_id", None)
        namespace = parent_tool_use_id if parent_tool_use_id else "root"

        # Calculate candidate start time
        parent_run = self.namespaces.get(namespace, self.namespaces["root"])
        child_runs = parent_run.child_runs or []
        if child_runs:
            candidate_start = (
                child_runs[-1].end_time.timestamp()
                if child_runs[-1].end_time
                else event_time
            )
        elif parent_run.start_time:
            candidate_start = parent_run.start_time.timestamp()
        else:
            candidate_start = event_time

        # Initialize history for this namespace
        if namespace not in self.history:
            self.history[namespace] = self.history["root"].copy()

        if msg_type == "AssistantMessage":
            self._handle_assistant_message(msg, namespace, candidate_start, event_time)
        elif msg_type == "UserMessage":
            self._handle_user_message(msg, namespace, event_time)

        # Add to history
        self.history[namespace].append(msg)

    def _handle_assistant_message(
        self,
        msg: Any,
        namespace: str,
        start_time: float,
        event_time: float,
    ) -> None:
        """Handle AssistantMessage: create or update LLM run, create tool runs."""
        run_key = self._get_run_key(msg, namespace)

        # Create or get assistant run
        if run_key not in self.assistant_runs:
            history_messages = convert_from_anthropic_message(self.history[namespace])
            self.assistant_runs[run_key] = self._create_child(
                namespace=namespace,
                name="claude.assistant.turn",
                run_type="llm",
                inputs={"messages": history_messages},
                start_time=start_time,
                outputs={"output": {"messages": []}},
            )

        run = self.assistant_runs[run_key]

        # Accumulate outputs
        prev_messages = (
            run.outputs.get("output", {}).get("messages", []) if run.outputs else []
        )
        new_messages = convert_from_anthropic_message([msg])
        run.outputs = {"output": {"messages": prev_messages + new_messages}}

        # Update end time
        run.end_time = datetime.fromtimestamp(event_time, tz=timezone.utc)

        # Set model name
        if run.extra is None:
            run.extra = {}
        run.extra.setdefault("metadata", {})

        model = getattr(msg.message, "model", None) if hasattr(msg, "message") else None
        if model:
            run.extra["metadata"]["ls_model_name"] = model

        # Extract usage
        usage = extract_usage_from_assistant_message(msg)
        run.extra["metadata"]["usage_metadata"] = usage

        # Process tool uses
        self._handle_tool_uses(msg, namespace, event_time)

    def _handle_tool_uses(self, msg: Any, namespace: str, event_time: float) -> None:
        """Process tool uses in an AssistantMessage."""
        if not hasattr(msg, "content"):
            return

        parent_tool_use_id = getattr(msg, "parent_tool_use_id", None)

        for block in msg.content:
            if not is_tool_block(block):
                continue

            tool_use_id = getattr(block, "id", None)
            if not tool_use_id:
                continue

            tool_name = getattr(block, "name", "unknown-tool")
            tool_input = getattr(block, "input", {})

            # Mark this tool as managed by StreamManager
            self._managed_tool_ids.add(tool_use_id)

            if is_task_tool(block) and not parent_tool_use_id:
                # This is a Task tool (subagent) at root level
                subagent_name = (
                    tool_input.get("subagent_type")
                    or tool_input.get("agent_type")
                    or (
                        tool_input.get("description", "").split()[0]
                        if tool_input.get("description")
                        else None
                    )
                    or "unknown-agent"
                )

                if tool_use_id not in self.tools:
                    self.tools[tool_use_id] = self._create_child(
                        namespace="root",
                        name=subagent_name,
                        run_type="chain",
                        inputs=tool_input,
                        start_time=event_time,
                    )
                    # Register this tool's run as a namespace for child messages
                    self.namespaces[tool_use_id] = self.tools[tool_use_id]
            else:
                # Regular tool
                if tool_use_id not in self.tools:
                    self.tools[tool_use_id] = self._create_child(
                        namespace=namespace,
                        name=tool_name,
                        run_type="tool",
                        inputs={"input": tool_input} if tool_input else {},
                        start_time=event_time,
                    )

    def _handle_user_message(
        self,
        msg: Any,
        namespace: str,
        event_time: float,
    ) -> None:
        """Handle UserMessage: complete tool runs with results."""
        if not hasattr(msg, "content"):
            return

        # Find tool result blocks
        content = msg.content
        if not isinstance(content, list):
            return

        tool_result = None
        for block in content:
            block_type = type(block).__name__
            if block_type == "ToolResultBlock" or (
                isinstance(block, dict) and block.get("type") == "tool_result"
            ):
                tool_result = block
                break

        if not tool_result:
            return

        # Get tool_use_id
        tool_use_id = (
            tool_result.get("tool_use_id")
            if isinstance(tool_result, dict)
            else getattr(tool_result, "tool_use_id", None)
        )

        if not tool_use_id or tool_use_id not in self.tools:
            return

        # Get tool response
        tool_response = getattr(msg, "tool_use_result", None)
        if tool_response is None:
            # Try to get from block content
            tool_response = (
                tool_result.get("content")
                if isinstance(tool_result, dict)
                else getattr(tool_result, "content", None)
            )

        # Format output
        if isinstance(tool_response, dict):
            outputs = tool_response
        elif isinstance(tool_response, list):
            outputs = {"content": tool_response}
        else:
            outputs = {"output": str(tool_response)} if tool_response else {}

        # Check for error
        is_error = (
            tool_result.get("is_error", False)
            if isinstance(tool_result, dict)
            else getattr(tool_result, "is_error", False)
        )

        error_msg = None
        if is_error:
            if isinstance(tool_response, (str, int, float, bool)):
                error_msg = str(tool_response)
            elif tool_response is not None:
                try:
                    import json

                    error_msg = json.dumps(tool_response)
                except (TypeError, ValueError):
                    error_msg = str(tool_response)

        # Complete the tool run
        tool_run = self.tools[tool_use_id]
        tool_run.end(outputs=outputs, error=error_msg)
        tool_run.end_time = datetime.fromtimestamp(event_time, tz=timezone.utc)

    def _handle_result_message(self, msg: Any) -> None:
        """Handle ResultMessage: apply usage correction and metadata."""
        from ._messages import extract_usage_from_result_message

        # Get usage from modelUsage (per-model breakdown) or usage (aggregate)
        model_usage = getattr(msg, "model_usage", None)
        if model_usage is None:
            model_usage = getattr(msg, "modelUsage", None)

        # Calculate aggregate usage
        if model_usage:
            usage = aggregate_usage_from_model_usage(model_usage)
            # Apply usage correction to distribute tokens across runs
            correct_usage_from_results(
                model_usage,
                list(self.assistant_runs.values()),
            )
        else:
            # Fall back to extracting from msg.usage
            usage = extract_usage_from_result_message(msg)
            # Apply aggregate usage to the last assistant run (like old code)
            if self.assistant_runs and usage:
                last_run = list(self.assistant_runs.values())[-1]
                if last_run.extra is None:
                    last_run.extra = {}
                last_run.extra.setdefault("metadata", {})
                last_run.extra["metadata"]["usage_metadata"] = usage.copy()

        # Calculate aggregate usage for root run
        root_run = self.namespaces.get("root")
        if not root_run:
            return

        if root_run.extra is None:
            root_run.extra = {}
        root_run.extra.setdefault("metadata", {})

        # Add total_cost if available
        total_cost = getattr(msg, "total_cost_usd", None)
        if total_cost is not None:
            usage["total_cost"] = total_cost

        root_run.extra["metadata"]["usage_metadata"] = usage

        # Add conversation-level metadata
        metadata_attrs = (
            "is_error",
            "num_turns",
            "session_id",
            "duration_ms",
            "duration_api_ms",
        )
        for attr in metadata_attrs:
            val = getattr(msg, attr, None)
            if val is not None:
                root_run.extra["metadata"][attr] = val

    def get_final_output(self) -> Optional[dict[str, Any]]:
        """Get the final output from the last assistant message."""
        # Get all assistant run outputs
        for run in reversed(list(self.assistant_runs.values())):
            if run.outputs:
                messages = run.outputs.get("output", {}).get("messages", [])
                if messages:
                    return messages[-1]
        return None

    def get_managed_tool_ids(self) -> set[str]:
        """Get the set of tool_use_ids managed by this StreamManager."""
        return self._managed_tool_ids.copy()

    def finish(self) -> None:
        """Clean up incomplete tools and patch all runs."""
        # End incomplete tool runs
        for tool_use_id, tool_run in self.tools.items():
            if tool_run.outputs is None and tool_run.error is None:
                tool_run.end(error="Run not completed (conversation ended)")

        # Patch all runs
        for run_tree in self._run_trees:
            try:
                run_tree.patch()
            except Exception as e:
                logger.warning(f"Failed to patch run: {e}")
