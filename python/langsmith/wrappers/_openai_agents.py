"""Tombstone module for backward compatibility.

This module has been moved to langsmith.integrations.openai_agents.
Imports from this location are deprecated but will continue to work.
"""

from langsmith.integrations.openai_agents import OpenAIAgentsTracingProcessor

__all__ = ["OpenAIAgentsTracingProcessor"]
