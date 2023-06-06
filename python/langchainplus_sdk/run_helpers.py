"""Decorator for creating a run tree from functions."""

import contextvars
import inspect
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union
from uuid import UUID

from langchainplus_sdk.run_trees import RunTree
from langchainplus_sdk.schemas import RunTypeEnum

import asyncio
import threading
import contextvars


T = TypeVar("T")


class HybridContext(Generic[T]):
    def __init__(self):
        self.async_context = contextvars.ContextVar[T]("async_context", default=None)
        self.thread_context = threading.local()

    def set(self, value):
        if asyncio.get_event_loop().is_running():
            self.async_context.set(value)
            self.thread_context.value = value

    def get(self):
        if asyncio.get_event_loop().is_running():
            return self.async_context.get()
        else:
            return (
                self.thread_context.value
                if hasattr(self.thread_context, "value")
                else None
            )


def _get_inputs(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Return a dictionary of inputs from the function signature."""
    # TODO: Could inspect and map names...
    # TODO: Handle non-json-serializable inputs
    return {"args": args, "kwargs": kwargs}


parent_run_tree = HybridContext[RunTree]()


def run_tree(
    run_type: Union[RunTypeEnum, str],
    *,
    name: Optional[str] = None,
    extra: Optional[Dict] = None,
) -> Callable:
    """Decorator for creating or adding a run to a run tree."""
    extra_outer = extra or {}

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(
            *args: Any,
            session_name: Optional[str] = None,
            session_id: Optional[UUID] = None,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function"""
            parent_run = parent_run_tree.get()
            signature = inspect.signature(func)
            name_ = name or func.__name__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(*args, **kwargs)
            if parent_run is not None:
                new_run = parent_run.create_child(
                    name=name_,
                    run_type=run_type,
                    serialized={"name": name, "signature": str(signature)},
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={"name": name, "signature": str(signature)},
                    inputs=inputs,
                    run_type=run_type,
                    reference_example_id=reference_example_id,
                    session_id=session_id,
                    session_name=session_name,
                    extra=extra_inner,
                )
            new_run.post()
            parent_run_tree.set(new_run)
            try:
                if not kwargs:
                    function_result = await func(*args)
                else:
                    function_result = await func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                raise e
            parent_run_tree.set(parent_run)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        @wraps(func)
        def wrapper(
            *args: Any,
            session_name: Optional[str] = None,
            session_id: Optional[UUID] = None,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            parent_run = parent_run_tree.get()
            signature = inspect.signature(func)
            name_ = name or func.__name__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(*args, **kwargs)
            if parent_run is not None:
                new_run = parent_run.create_child(
                    name=name_,
                    run_type=run_type,
                    serialized={"name": name, "signature": str(signature)},
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={"name": name, "signature": str(signature)},
                    inputs=inputs,
                    run_type=run_type,
                    reference_example_id=reference_example_id,
                    session_id=session_id,
                    session_name=session_name,
                    extra=extra_inner,
                )
            new_run.post()
            parent_run_tree.set(new_run)
            try:
                if not kwargs:
                    function_result = func(*args)
                else:
                    function_result = func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                raise e
            parent_run_tree.set(parent_run)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator
