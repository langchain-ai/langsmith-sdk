"""Decorator for creating a run tree from functions."""
import contextlib
import contextvars
import functools
import inspect
import logging
import os
import traceback
import uuid
from concurrent import futures
from typing import Any, Callable, Dict, Generator, List, Mapping, Optional, TypedDict

from langsmith import client, run_trees, utils

logger = logging.getLogger(__name__)
_PARENT_RUN_TREE = contextvars.ContextVar[Optional[run_trees.RunTree]](
    "_PARENT_RUN_TREE", default=None
)
_PROJECT_NAME = contextvars.ContextVar[Optional[str]]("_PROJECT_NAME", default=None)
_TAGS = contextvars.ContextVar[Optional[List[str]]]("_TAGS", default=None)
_METADATA = contextvars.ContextVar[Optional[Dict[str, Any]]]("_METADATA", default=None)


def get_run_tree_context() -> Optional[run_trees.RunTree]:
    """Get the current run tree context."""
    return _PARENT_RUN_TREE.get()


def _get_inputs(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> Dict[str, Any]:
    """Return a dictionary of inputs from the function signature."""
    bound = signature.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    arguments = dict(bound.arguments)
    arguments.pop("self", None)
    arguments.pop("cls", None)
    for param_name, param in signature.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            # Update with the **kwargs, and remove the original entry
            # This is to help flatten out keyword arguments
            if param_name in arguments:
                arguments.update(arguments[param_name])
                arguments.pop(param_name)

    return arguments


class LangSmithExtra(TypedDict, total=False):
    """Any additional info to be injected into the run dynamically."""

    reference_example_id: Optional[client.ID_TYPE]
    run_extra: Optional[Dict]
    run_tree: Optional[run_trees.RunTree]
    project_name: Optional[str]
    metadata: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    run_id: Optional[client.ID_TYPE]
    client: Optional[client.Client]


class _TraceableContainer(TypedDict, total=False):
    """Typed response when initializing a run a traceable."""

    new_run: run_trees.RunTree
    project_name: Optional[str]
    outer_project: Optional[str]
    outer_metadata: Optional[Dict[str, Any]]
    outer_tags: Optional[List[str]]


def _collect_extra(extra_outer: dict, langsmith_extra: LangSmithExtra) -> dict:
    run_extra = langsmith_extra.get("run_extra", None)
    if run_extra:
        extra_inner = {**extra_outer, **run_extra}
    else:
        extra_inner = extra_outer
    return extra_inner


def _setup_run(
    func: Callable,
    run_type: str,
    extra_outer: dict,
    langsmith_extra: Optional[LangSmithExtra] = None,
    name: Optional[str] = None,
    executor: Optional[futures.ThreadPoolExecutor] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    tags: Optional[List[str]] = None,
    client: Optional[client.Client] = None,
    args: Any = None,
    kwargs: Any = None,
) -> _TraceableContainer:
    outer_project = _PROJECT_NAME.get() or os.environ.get(
        "LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "default")
    )
    langsmith_extra = langsmith_extra or LangSmithExtra()
    parent_run_ = langsmith_extra.get("run_tree") or _PARENT_RUN_TREE.get()
    project_name_ = langsmith_extra.get("project_name", outer_project)
    signature = inspect.signature(func)
    name_ = name or func.__name__
    docstring = func.__doc__
    extra_inner = _collect_extra(extra_outer, langsmith_extra)
    outer_metadata = _METADATA.get()
    metadata_ = {
        **(langsmith_extra.get("metadata") or {}),
        **(outer_metadata or {}),
    }
    _METADATA.set(metadata_)
    metadata_.update(metadata or {})
    metadata_["ls_method"] = "traceable"
    extra_inner["metadata"] = metadata_
    inputs = _get_inputs(signature, *args, **kwargs)
    outer_tags = _TAGS.get()
    tags_ = (langsmith_extra.get("tags") or []) + (outer_tags or [])
    _TAGS.set(tags_)
    tags_ += tags or []
    id_ = langsmith_extra.get("run_id", uuid.uuid4())
    client_ = langsmith_extra.get("client", client)
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
            tags=tags_,
            extra=extra_inner,
            run_id=id_,
        )
    else:
        new_run = run_trees.RunTree(
            id=id_,
            name=name_,
            serialized={
                "name": name,
                "signature": str(signature),
                "doc": docstring,
            },
            inputs=inputs,
            run_type=run_type,
            reference_example_id=langsmith_extra.get("reference_example_id"),
            project_name=project_name_,
            extra=extra_inner,
            tags=tags_,
            executor=executor,
            client=client_,
        )
    new_run.post()
    return _TraceableContainer(
        new_run=new_run,
        project_name=project_name_,
        outer_project=outer_project,
        outer_metadata=outer_metadata,
        outer_tags=outer_tags,
    )


def traceable(
    run_type: str = "chain",
    *,
    name: Optional[str] = None,
    executor: Optional[futures.ThreadPoolExecutor] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    tags: Optional[List[str]] = None,
    client: Optional[client.Client] = None,
    extra: Optional[Dict] = None,
) -> Callable:
    """Decorator for creating or adding a run to a run tree."""
    extra_outer = extra or {}

    def decorator(func: Callable):
        if not utils.tracing_is_enabled():
            utils.log_once(
                logging.DEBUG, "Tracing is disabled, returning original function"
            )
            return func

        @functools.wraps(func)
        async def async_wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function"""

            run_container = _setup_run(
                func,
                run_type=run_type,
                langsmith_extra=langsmith_extra,
                extra_outer=extra_outer,
                name=name,
                executor=executor,
                metadata=metadata,
                tags=tags,
                client=client,
                args=args,
                kwargs=kwargs,
            )
            _PROJECT_NAME.set(run_container["project_name"])
            _PARENT_RUN_TREE.set(run_container["new_run"])
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = await func(
                        *args, run_tree=run_container["new_run"], **kwargs
                    )
                else:
                    function_result = await func(*args, **kwargs)
            except Exception as e:
                run_container["new_run"].end(error=str(e))
                run_container["new_run"].patch()
                _PARENT_RUN_TREE.set(run_container["new_run"].parent_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                raise e
            _PARENT_RUN_TREE.set(run_container["new_run"].parent_run)
            _PROJECT_NAME.set(run_container["outer_project"])
            if isinstance(function_result, dict):
                run_container["new_run"].end(outputs=function_result)
            else:
                run_container["new_run"].end(outputs={"output": function_result})
            run_container["new_run"].patch()
            return function_result

        @functools.wraps(func)
        def wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            run_container = _setup_run(
                func,
                run_type=run_type,
                langsmith_extra=langsmith_extra,
                extra_outer=extra_outer,
                name=name,
                executor=executor,
                metadata=metadata,
                tags=tags,
                client=client,
                args=args,
                kwargs=kwargs,
            )
            _PROJECT_NAME.set(run_container["project_name"])
            _PARENT_RUN_TREE.set(run_container["new_run"])
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = func(
                        *args, run_tree=run_container["new_run"], **kwargs
                    )
                else:
                    function_result = func(*args, **kwargs)
            except (BaseException, Exception, KeyboardInterrupt) as e:
                stacktrace = traceback.format_exc()
                run_container["new_run"].end(error=stacktrace)
                run_container["new_run"].patch()
                _PARENT_RUN_TREE.set(run_container["new_run"].parent_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
                raise e
            _PARENT_RUN_TREE.set(run_container["new_run"].parent_run)
            _PROJECT_NAME.set(run_container["outer_project"])
            _TAGS.set(run_container["outer_tags"])
            _METADATA.set(run_container["outer_metadata"])
            if isinstance(function_result, dict):
                run_container["new_run"].end(outputs=function_result)
            else:
                run_container["new_run"].end(outputs={"output": function_result})
            run_container["new_run"].patch()
            return function_result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


@contextlib.contextmanager
def trace(
    name: str,
    run_type: str,
    *,
    inputs: Optional[Dict] = None,
    extra: Optional[Dict] = None,
    executor: Optional[futures.ThreadPoolExecutor] = None,
    project_name: Optional[str] = None,
    run_tree: Optional[run_trees.RunTree] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Generator[run_trees.RunTree, None, None]:
    """Context manager for creating a run tree."""
    outer_tags = _TAGS.get()
    outer_metadata = _METADATA.get()
    outer_project = _PROJECT_NAME.get() or os.environ.get(
        "LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "default")
    )
    parent_run_ = _PARENT_RUN_TREE.get() if run_tree is None else run_tree

    # Merge and set context varaibles
    tags_ = sorted(set((tags or []) + (outer_tags or [])))
    _TAGS.set(tags_)
    metadata = {**(metadata or {}), **(outer_metadata or {}), "ls_method": "trace"}
    _METADATA.set(metadata)

    extra_outer = extra or {}
    extra_outer["metadata"] = metadata

    project_name_ = project_name or outer_project
    if parent_run_ is not None:
        new_run = parent_run_.create_child(
            name=name,
            run_type=run_type,
            extra=extra_outer,
            inputs=inputs,
            tags=tags_,
        )
    else:
        new_run = run_trees.RunTree(
            name=name,
            run_type=run_type,
            extra=extra_outer,
            executor=executor,
            project_name=project_name_,
            inputs=inputs or {},
            tags=tags_,
        )
    new_run.post()
    _PARENT_RUN_TREE.set(new_run)
    _PROJECT_NAME.set(project_name_)
    try:
        yield new_run
    except (Exception, KeyboardInterrupt, BaseException) as e:
        tb = traceback.format_exc()
        new_run.end(error=tb)
        new_run.patch()
        _PARENT_RUN_TREE.set(parent_run_)
        _PROJECT_NAME.set(outer_project)
        _TAGS.set(outer_tags)
        _METADATA.set(outer_metadata)
        raise e
    _PARENT_RUN_TREE.set(parent_run_)
    _PROJECT_NAME.set(outer_project)
    _TAGS.set(outer_tags)
    _METADATA.set(outer_metadata)
    if new_run.end_time is None:
        # User didn't call end() on the run, so we'll do it for them
        new_run.end()
    new_run.patch()
