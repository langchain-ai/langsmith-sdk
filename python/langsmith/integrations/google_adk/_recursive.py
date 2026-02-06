"""Recursive callback injection for Google ADK agent hierarchies."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RecursiveCallbackInjector:
    """Inject callbacks into agent hierarchies recursively."""

    def __init__(self, callbacks: dict[str, Callable[..., Any]]):
        self._callbacks = callbacks
        self._seen_ids: set[int] = set()

    def inject(self, root_agent: Any) -> None:
        self._process_agent(root_agent)

    def _process_agent(self, agent: Any) -> None:
        agent_id = id(agent)
        if agent_id in self._seen_ids:
            return
        self._seen_ids.add(agent_id)

        self._add_callbacks(agent)
        self._process_sub_agents(agent)
        self._process_tools(agent)

    def _add_callbacks(self, agent: Any) -> None:
        for name, callback in self._callbacks.items():
            try:
                current = getattr(agent, name, None)
                if current is None:
                    setattr(agent, name, callback)
                elif isinstance(current, list):
                    current.append(callback)
                elif callable(current):
                    setattr(agent, name, [current, callback])
                else:
                    setattr(agent, name, callback)
            except Exception as e:
                logger.debug(f"Failed to inject callback {name}: {e}")

    def _process_sub_agents(self, agent: Any) -> None:
        for sub_agent in getattr(agent, "sub_agents", None) or []:
            if sub_agent is not None:
                self._process_agent(sub_agent)

    def _process_tools(self, agent: Any) -> None:
        for tool in getattr(agent, "tools", None) or []:
            if tool is None:
                continue
            if nested := getattr(tool, "agent", None):
                self._process_agent(nested)
            for sub in getattr(tool, "sub_agents", None) or []:
                if sub is not None:
                    self._process_agent(sub)


def get_callbacks() -> dict[str, Callable[..., Any]]:
    """Get LangSmith tracing callbacks (agent + tool only; LLM uses flow wrapper)."""
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
