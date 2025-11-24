"""This module provides integration wrappers for popular open source eval frameworks.

To be used with LangSmith.
"""

from langsmith.evaluation.integrations._langchain import LangChainStringEvaluator

__all__ = ["LangChainStringEvaluator"]
