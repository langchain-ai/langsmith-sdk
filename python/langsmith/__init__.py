"""LangSmith Client."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langsmith._expect import expect
    from langsmith.async_client import AsyncClient
    from langsmith.client import Client
    from langsmith.evaluation import (
        aevaluate,
        aevaluate_existing,
        evaluate,
        evaluate_existing,
    )
    from langsmith.evaluation.evaluator import EvaluationResult, RunEvaluator
    from langsmith.prompt_cache import AsyncPromptCache, PromptCache
    from langsmith.run_helpers import (
        get_current_run_tree,
        get_tracing_context,
        set_run_metadata,
        trace,
        traceable,
        tracing_context,
    )
    from langsmith.run_trees import RunTree, configure
    from langsmith.testing._internal import test, unit
    from langsmith.utils import ContextThreadPoolExecutor
    from langsmith.uuid import uuid7, uuid7_from_datetime

# Avoid calling into importlib on every call to __version__

__version__ = "0.7.7"
version = __version__  # for backwards compatibility


def __getattr__(name: str) -> Any:
    if name == "__version__":
        return version
    elif name == "Client":
        from langsmith.client import Client

        return Client
    elif name == "AsyncClient":
        from langsmith.async_client import AsyncClient

        return AsyncClient
    elif name == "RunTree":
        from langsmith.run_trees import RunTree

        return RunTree
    elif name == "EvaluationResult":
        from langsmith.evaluation.evaluator import EvaluationResult

        return EvaluationResult
    elif name == "RunEvaluator":
        from langsmith.evaluation.evaluator import RunEvaluator

        return RunEvaluator
    elif name == "trace":
        from langsmith.run_helpers import trace

        return trace
    elif name == "traceable":
        from langsmith.run_helpers import traceable

        return traceable

    elif name == "test":
        from langsmith.testing._internal import test

        return test

    elif name == "expect":
        from langsmith._expect import expect

        return expect
    elif name == "evaluate":
        from langsmith.evaluation import evaluate

        return evaluate

    elif name == "evaluate_existing":
        from langsmith.evaluation import evaluate_existing

        return evaluate_existing
    elif name == "aevaluate":
        from langsmith.evaluation import aevaluate

        return aevaluate
    elif name == "aevaluate_existing":
        from langsmith.evaluation import aevaluate_existing

        return aevaluate_existing
    elif name == "tracing_context":
        from langsmith.run_helpers import tracing_context

        return tracing_context

    elif name == "get_tracing_context":
        from langsmith.run_helpers import get_tracing_context

        return get_tracing_context
    elif name == "get_current_run_tree":
        from langsmith.run_helpers import get_current_run_tree

        return get_current_run_tree
    elif name == "set_run_metadata":
        from langsmith.run_helpers import set_run_metadata

        return set_run_metadata

    elif name == "unit":
        from langsmith.testing._internal import unit

        return unit
    elif name == "ContextThreadPoolExecutor":
        from langsmith.utils import ContextThreadPoolExecutor

        return ContextThreadPoolExecutor
    elif name == "configure":
        from langsmith.run_trees import configure

        return configure
    elif name == "uuid7":
        from langsmith.uuid import uuid7

        return uuid7
    elif name == "uuid7_from_datetime":
        from langsmith.uuid import uuid7_from_datetime

        return uuid7_from_datetime
    elif name == "PromptCache":
        from langsmith.prompt_cache import PromptCache

        return PromptCache
    elif name == "AsyncPromptCache":
        from langsmith.prompt_cache import AsyncPromptCache

        return AsyncPromptCache
    elif name == "Cache":
        from langsmith.prompt_cache import Cache

        return Cache
    elif name == "AsyncCache":
        from langsmith.prompt_cache import AsyncCache

        return AsyncCache

    elif name == "configure_global_prompt_cache":
        from langsmith.prompt_cache import configure_global_prompt_cache

        return configure_global_prompt_cache

    elif name == "configure_global_async_prompt_cache":
        from langsmith.prompt_cache import configure_global_async_prompt_cache

        return configure_global_async_prompt_cache

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Client",
    "AsyncClient",
    "PromptCache",
    "AsyncPromptCache",
    "Cache",
    "AsyncCache",
    "configure_global_prompt_cache",
    "configure_global_async_prompt_cache",
    "RunTree",
    "configure",
    "__version__",
    "EvaluationResult",
    "RunEvaluator",
    "anonymizer",
    "traceable",
    "trace",
    "unit",
    "test",
    "expect",
    "evaluate",
    "evaluate_existing",
    "aevaluate_existing",
    "aevaluate",
    "tracing_context",
    "get_tracing_context",
    "get_current_run_tree",
    "set_run_metadata",
    "ContextThreadPoolExecutor",
    "uuid7",
    "uuid7_from_datetime",
]
