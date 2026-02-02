"""Recursive callback injection for Google ADK agent hierarchies."""

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RecursiveCallbackInjector:
    """Recursively inject callbacks into agent hierarchies.

    This class traverses an agent's sub-agents and tools to ensure
    all nested agents receive the tracing callbacks.
    """

    def __init__(self, callbacks: dict[str, Callable[..., Any]]):
        """Initialize the injector with callbacks to add.

        Args:
            callbacks: Dictionary mapping callback attribute names to callback
                functions. E.g., {"before_agent_callback": my_callback}
        """
        self._callbacks = callbacks
        self._seen_ids: set[int] = set()

    def inject(self, root_agent: Any) -> None:
        """Inject callbacks into the agent hierarchy starting from root.

        Args:
            root_agent: The root agent to start injection from.
        """
        self._process_agent(root_agent)

    def _process_agent(self, agent: Any) -> None:
        """Process a single agent, adding callbacks and recursing into children.

        Args:
            agent: The agent to process.
        """
        agent_id = id(agent)
        if agent_id in self._seen_ids:
            return

        # Add to seen BEFORE processing children to prevent infinite recursion
        self._seen_ids.add(agent_id)

        self._add_callbacks(agent)
        self._process_sub_agents(agent)
        self._process_tools(agent)

    def _add_callbacks(self, agent: Any) -> None:
        """Add callbacks to an agent, handling None/list/callable cases.

        Google ADK agents support callbacks as:
        - None (no callback)
        - A single callable
        - A list of callables

        This method handles all cases and appends our callbacks appropriately.

        Args:
            agent: The agent to add callbacks to.
        """
        for name, callback in self._callbacks.items():
            try:
                current = getattr(agent, name, None)

                if current is None:
                    # No existing callback - set ours directly
                    setattr(agent, name, callback)
                elif isinstance(current, list):
                    # Existing list of callbacks - append ours
                    current.append(callback)
                elif callable(current):
                    # Single existing callback - convert to list with both
                    setattr(agent, name, [current, callback])
                else:
                    # Unknown type - try to set anyway
                    logger.debug(
                        f"Unexpected callback type for {name}: {type(current)}"
                    )
                    setattr(agent, name, callback)
            except AttributeError:
                # Agent doesn't support this callback attribute
                logger.debug(f"Agent {type(agent).__name__} doesn't support {name}")
            except Exception as e:
                logger.warning(f"Failed to inject callback {name}: {e}")

    def _process_sub_agents(self, agent: Any) -> None:
        """Recursively process sub-agents.

        Args:
            agent: The parent agent whose sub-agents to process.
        """
        sub_agents = getattr(agent, "sub_agents", None)
        if not sub_agents:
            return

        for sub_agent in sub_agents:
            if sub_agent is not None:
                self._process_agent(sub_agent)

    def _process_tools(self, agent: Any) -> None:
        """Process tools that may contain nested agents (like AgentTool).

        Args:
            agent: The agent whose tools to process.
        """
        tools = getattr(agent, "tools", None)
        if not tools:
            return

        for tool in tools:
            if tool is None:
                continue

            # Check for AgentTool which wraps another agent
            nested_agent = getattr(tool, "agent", None)
            if nested_agent is not None:
                self._process_agent(nested_agent)

            # Some tools might have sub_agents directly
            tool_sub_agents = getattr(tool, "sub_agents", None)
            if tool_sub_agents:
                for sub_agent in tool_sub_agents:
                    if sub_agent is not None:
                        self._process_agent(sub_agent)


def get_callbacks() -> dict[str, Callable[..., Any]]:
    """Get the dictionary of LangSmith tracing callbacks.

    Note: Model callbacks are NOT included here because LLM tracing
    is handled by the flow-level wrapper (wrap_flow_call_llm_async)
    which provides better TTFT (time to first token) tracking.

    Returns:
        Dictionary mapping callback attribute names to callback functions.
    """
    from ._hooks import (
        after_agent_callback,
        after_tool_callback,
        before_agent_callback,
        before_tool_callback,
    )

    return {
        "before_agent_callback": before_agent_callback,
        "after_agent_callback": after_agent_callback,
        "before_tool_callback": before_tool_callback,
        "after_tool_callback": after_tool_callback,
    }
