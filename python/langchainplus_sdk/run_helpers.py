"""Decorator for creating a run tree from functions."""
import contextvars
import inspect
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union
from uuid import UUID

from langchainplus_sdk.run_trees import RunTree
from langchainplus_sdk.schemas import RunTypeEnum

parent_run_tree = contextvars.ContextVar[Optional[RunTree]](
    "parent_run_tree", default=None
)


def _get_inputs(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Return a dictionary of inputs from the function signature."""
    # TODO: Could inspect and map names...
    # TODO: Handle non-json-serializable inputs
    return {"args": args, "kwargs": kwargs}


def traceable(
    run_type: Union[RunTypeEnum, str],
    *,
    name: Optional[str] = None,
    extra: Optional[Dict] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> Callable:
    """Decorator for creating or adding a run to a run tree."""
    extra_outer = extra or {}

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(
            *args: Any,
            session_name: Optional[str] = None,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            run_tree: Optional[RunTree] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function"""
            if run_tree is None:
                parent_run_ = parent_run_tree.get()
            else:
                parent_run_ = run_tree
            signature = inspect.signature(func)
            name_ = name or func.__name__
            docstring = func.__doc__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(*args, **kwargs)
            if parent_run_ is not None:
                new_run = parent_run_.create_child(
                    name=name_,
                    run_type=run_type,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    run_type=run_type,
                    reference_example_id=reference_example_id,
                    session_name=session_name,
                    extra=extra_inner,
                    executor=executor,
                )
            new_run.post()
            parent_run_tree.set(new_run)
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = await func(*args, run_tree=new_run, **kwargs)
                else:
                    function_result = await func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                raise e
            parent_run_tree.set(parent_run_)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        @wraps(func)
        def wrapper(
            *args: Any,
            session_name: Optional[str] = None,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            run_tree: Optional[RunTree] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            if run_tree is None:
                parent_run_ = parent_run_tree.get()
            else:
                parent_run_ = run_tree
            signature = inspect.signature(func)
            name_ = name or func.__name__
            docstring = func.__doc__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(*args, **kwargs)
            if parent_run_ is not None:
                new_run = parent_run_.create_child(
                    name=name_,
                    run_type=run_type,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    run_type=run_type,
                    reference_example_id=reference_example_id,
                    session_name=session_name,
                    extra=extra_inner,
                    executor=executor,
                )
            new_run.post()
            parent_run_tree.set(new_run)
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = func(*args, run_tree=new_run, **kwargs)
                else:
                    function_result = func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                raise e
            parent_run_tree.set(parent_run_)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator
