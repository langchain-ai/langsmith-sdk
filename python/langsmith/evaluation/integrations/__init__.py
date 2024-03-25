"""
This module provides integration wrappers for popular open source evaluator frameworks
to be used with LangSmith.
"""

from langsmith.evaluation.integrations._langchain import LangChainStringEvaluator

__all__ = ["LangChainStringEvaluator"]
