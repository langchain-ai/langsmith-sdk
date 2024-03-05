"""Decorator for creating a run tree from functions."""

from __future__ import annotations

import contextlib
import contextvars
import datetime
import functools
import inspect
import logging
import traceback
import uuid
import warnings
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from langsmith import client as ls_client
from langsmith import run_trees, utils

if TYPE_CHECKING:
    from langchain.schema.runnable import Runnable

logger = logging.getLogger(__name__)
_PARENT_RUN_TREE = contextvars.ContextVar[Optional[run_trees.RunTree]](
    "_PARENT_RUN_TREE", default=None
)
_PROJECT_NAME = contextvars.ContextVar[Optional[str]]("_PROJECT_NAME", default=None)
_TAGS = contextvars.ContextVar[Optional[List[str]]]("_TAGS", default=None)
_METADATA = contextvars.ContextVar[Optional[Dict[str, Any]]]("_METADATA", default=None)


def get_current_run_tree() -> Optional[run_trees.RunTree]:
    """Get the current run tree context."""
    return _PARENT_RUN_TREE.get()


get_run_tree_context = get_current_run_tree


def _is_traceable_function(func: Callable) -> bool:
    return getattr(func, "__langsmith_traceable__", False)


def is_traceable_function(func: Callable) -> bool:
    """Check if a function is @traceable decorated."""
    return (
        _is_traceable_function(func)
        or (isinstance(func, functools.partial) and _is_traceable_function(func.func))
        or (hasattr(func, "__call__") and _is_traceable_function(func.__call__))
    )


def is_async(func: Callable) -> bool:
    """Inspect function or wrapped function to see if it is async."""
    return inspect.iscoroutinefunction(func) or (
        hasattr(func, "__wrapped__") and inspect.iscoroutinefunction(func.__wrapped__)
    )


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

    reference_example_id: Optional[ls_client.ID_TYPE]
    run_extra: Optional[Dict]
    run_tree: Optional[run_trees.RunTree]
    project_name: Optional[str]
    metadata: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    run_id: Optional[ls_client.ID_TYPE]
    client: Optional[ls_client.Client]


class _TraceableContainer(TypedDict, total=False):
    """Typed response when initializing a run a traceable."""

    new_run: Optional[run_trees.RunTree]
    project_name: Optional[str]
    outer_project: Optional[str]
    outer_metadata: Optional[Dict[str, Any]]
    outer_tags: Optional[List[str]]


class _ContainerInput(TypedDict, total=False):
    """Typed response when initializing a run a traceable."""

    extra_outer: Optional[Dict]
    name: Optional[str]
    metadata: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    client: Optional[ls_client.Client]
    reduce_fn: Optional[Callable]
    project_name: Optional[str]
    run_type: ls_client.RUN_TYPE_T
    process_inputs: Optional[Callable[[dict], dict]]


def _container_end(
    container: _TraceableContainer,
    outputs: Optional[Any] = None,
    error: Optional[str] = None,
):
    """End the run."""
    run_tree = container.get("new_run")
    if run_tree is None:
        # Tracing disabled
        return
    outputs_ = outputs if isinstance(outputs, dict) else {"output": outputs}
    run_tree.end(outputs=outputs_, error=error)
    run_tree.patch()
    if error:
        try:
            logger.info(f"See trace: {run_tree.get_url()}")
        except Exception:
            pass


def _collect_extra(extra_outer: dict, langsmith_extra: LangSmithExtra) -> dict:
    run_extra = langsmith_extra.get("run_extra", None)
    if run_extra:
        extra_inner = {**extra_outer, **run_extra}
    else:
        extra_inner = extra_outer
    return extra_inner


def _setup_run(
    func: Callable,
    container_input: _ContainerInput,
    langsmith_extra: Optional[LangSmithExtra] = None,
    args: Any = None,
    kwargs: Any = None,
) -> _TraceableContainer:
    """Create a new run or create_child() if run is passed in kwargs."""
    extra_outer = container_input.get("extra_outer") or {}
    name = container_input.get("name")
    metadata = container_input.get("metadata")
    tags = container_input.get("tags")
    client = container_input.get("client")
    run_type = container_input.get("run_type") or "chain"
    outer_project = _PROJECT_NAME.get()
    langsmith_extra = langsmith_extra or LangSmithExtra()
    parent_run_ = langsmith_extra.get("run_tree") or get_run_tree_context()
    selected_project = (
        _PROJECT_NAME.get()  # From parent trace
        or langsmith_extra.get("project_name")  # at invocation time
        or container_input["project_name"]  # at decorator time
        or utils.get_tracer_project()  # default
    )
    if not parent_run_ and not utils.tracing_is_enabled():
        utils.log_once(
            logging.DEBUG, "LangSmith tracing is disabled, returning original function."
        )
        return _TraceableContainer(
            new_run=None,
            project_name=selected_project,
            outer_project=outer_project,
            outer_metadata=None,
            outer_tags=None,
        )
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
    try:
        inputs = _get_inputs(signature, *args, **kwargs)
    except TypeError as e:
        logger.debug(f"Failed to infer inputs for {name_}: {e}")
        inputs = {"args": args, "kwargs": kwargs}
    process_inputs = container_input.get("process_inputs")
    if process_inputs:
        try:
            inputs = process_inputs(inputs)
        except Exception as e:
            logger.error(f"Failed to filter inputs for {name_}: {e}")
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
            project_name=selected_project,
            extra=extra_inner,
            tags=tags_,
            client=client_,
        )
    try:
        new_run.post()
    except Exception as e:
        logger.error(f"Failed to post run {new_run.id}: {e}")
    response_container = _TraceableContainer(
        new_run=new_run,
        project_name=selected_project,
        outer_project=outer_project,
        outer_metadata=outer_metadata,
        outer_tags=outer_tags,
    )
    _PROJECT_NAME.set(response_container["project_name"])
    _PARENT_RUN_TREE.set(response_container["new_run"])
    return response_container


R = TypeVar("R", covariant=True)

_VALID_RUN_TYPES = {
    "tool",
    "chain",
    "llm",
    "retriever",
    "embedding",
    "prompt",
    "parser",
}


@runtime_checkable
class SupportsLangsmithExtra(Protocol, Generic[R]):
    """Implementations of this Protoc accept an optional langsmith_extra parameter.

    Args:
        *args: Variable length arguments.
        langsmith_extra (Optional[Dict[str, Any]]): Optional dictionary of
            additional parameters for Langsmith.
        **kwargs: Keyword arguments.

    Returns:
        R: The return type of the callable.
    """

    def __call__(
        self,
        *args: Any,
        langsmith_extra: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> R:
        """Call the instance when it is called as a function.

        Args:
            *args: Variable length argument list.
            langsmith_extra: Optional dictionary containing additional
                parameters specific to Langsmith.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            R: The return value of the method.

        """
        ...


@overload
def traceable(
    func: Callable[..., R],
) -> Callable[..., R]:
    ...


@overload
def traceable(
    run_type: ls_client.RUN_TYPE_T = "chain",
    *,
    name: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    tags: Optional[List[str]] = None,
    client: Optional[ls_client.Client] = None,
    reduce_fn: Optional[Callable] = None,
    project_name: Optional[str] = None,
    process_inputs: Optional[Callable[[dict], dict]] = None,
) -> Callable[[Callable[..., R]], SupportsLangsmithExtra[R]]:
    ...


def traceable(
    *args: Any,
    **kwargs: Any,
) -> Union[Callable, Callable[[Callable], Callable]]:
    """Trace a function with langsmith.

    Args:
        run_type: The type of run (span) to create. Examples: llm, chain, tool, prompt,
            retriever, etc. Defaults to "chain".
        name: The name of the run. Defaults to the function name.
        metadata: The metadata to add to the run. Defaults to None.
        tags: The tags to add to the run. Defaults to None.
        client: The client to use for logging the run to LangSmith. Defaults to
            None, which will use the default client.
        reduce_fn: A function to reduce the output of the function if the function
            returns a generator. Defaults to None, which means the values will be
                logged as a list. Note: if the iterator is never exhausted (e.g.
                the function returns an infinite generator), this will never be
                called, and the run itself will be stuck in a pending state.
        project_name: The name of the project to log the run to. Defaults to None,
            which will use the default project.
        process_inputs: A function to filter the inputs to the run. Defaults to None.


    Returns:
            Union[Callable, Callable[[Callable], Callable]]: The decorated function.

    Note:
            - Requires that LANGCHAIN_TRACING_V2 be set to 'true' in the environment.

    Examples:
        .. code-block:: python
            import httpx
            import asyncio

            from typing import Iterable
            from langsmith import traceable, Client


            # Basic usage:
            @traceable
            def my_function(x: float, y: float) -> float:
                return x + y


            my_function(5, 6)


            @traceable
            async def my_async_function(query_params: dict) -> dict:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        "https://api.example.com/data",
                        params=query_params,
                    )
                    return response.json()


            asyncio.run(my_async_function({"param": "value"}))


            # Streaming data with a generator:
            @traceable
            def my_generator(n: int) -> Iterable:
                for i in range(n):
                    yield i


            for item in my_generator(5):
                print(item)


            # Async streaming data
            @traceable
            async def my_async_generator(query_params: dict) -> Iterable:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        "https://api.example.com/data",
                        params=query_params,
                    )
                    for item in response.json():
                        yield item


            async def async_code():
                async for item in my_async_generator({"param": "value"}):
                    print(item)


            asyncio.run(async_code())


            # Specifying a run type and name:
            @traceable(name="CustomName", run_type="tool")
            def another_function(a: float, b: float) -> float:
                return a * b


            another_function(5, 6)


            # Logging with custom metadata and tags:
            @traceable(
                metadata={"version": "1.0", "author": "John Doe"},
                tags=["beta", "test"]
            )
            def tagged_function(x):
                return x**2


            tagged_function(5)

            # Specifying a custom client and project name:
            custom_client = Client(api_key="your_api_key")


            @traceable(client=custom_client, project_name="My Special Project")
            def project_specific_function(data):
                return data


            project_specific_function({"data": "to process"})


            # Manually passing langsmith_extra:
            @traceable
            def manual_extra_function(x):
                return x**2


            manual_extra_function(5, langsmith_extra={"metadata": {"version": "1.0"}})
    """
    run_type: ls_client.RUN_TYPE_T = (
        args[0]
        if args and isinstance(args[0], str)
        else (kwargs.pop("run_type", None) or "chain")
    )
    if run_type not in _VALID_RUN_TYPES:
        warnings.warn(
            f"Unrecognized run_type: {run_type}. Must be one of: {_VALID_RUN_TYPES}."
            f" Did you mean @traceable(name='{run_type}')?"
        )
    if len(args) > 1:
        warnings.warn(
            "The `traceable()` decorator only accepts one positional argument, "
            "which should be the run_type. All other arguments should be passed "
            "as keyword arguments."
        )
    if "extra" in kwargs:
        warnings.warn(
            "The `extra` keyword argument is deprecated. Please use `metadata` "
            "instead.",
            DeprecationWarning,
        )
    reduce_fn = kwargs.pop("reduce_fn", None)
    container_input = _ContainerInput(
        # TODO: Deprecate raw extra
        extra_outer=kwargs.pop("extra", None),
        name=kwargs.pop("name", None),
        metadata=kwargs.pop("metadata", None),
        tags=kwargs.pop("tags", None),
        client=kwargs.pop("client", None),
        project_name=kwargs.pop("project_name", None),
        run_type=run_type,
        process_inputs=kwargs.pop("process_inputs", None),
    )
    if kwargs:
        warnings.warn(
            f"The following keyword arguments are not recognized and will be ignored: "
            f"{sorted(kwargs.keys())}.",
            DeprecationWarning,
        )

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function."""
            context_run = get_run_tree_context()
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
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
                stacktrace = traceback.format_exc()
                _container_end(run_container, error=stacktrace)
                raise e
            finally:
                _PARENT_RUN_TREE.set(context_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
            _container_end(run_container, outputs=function_result)
            return function_result

        @functools.wraps(func)
        async def async_generator_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> AsyncGenerator:
            context_run = get_run_tree_context()
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            results: List[Any] = []
            try:
                if func_accepts_parent_run:
                    async_gen_result = func(
                        *args, run_tree=run_container["new_run"], **kwargs
                    )
                else:
                    # TODO: Nesting is ambiguous if a nested traceable function is only
                    # called mid-generation. Need to explicitly accept run_tree to get
                    # around this.
                    async_gen_result = func(*args, **kwargs)
                _PARENT_RUN_TREE.set(context_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
                # Can't iterate through if it's a coroutine
                if inspect.iscoroutine(async_gen_result):
                    async_gen_result = await async_gen_result
                async for item in async_gen_result:
                    if run_type == "llm":
                        if run_container["new_run"]:
                            run_container["new_run"].add_event(
                                {
                                    "name": "new_token",
                                    "time": datetime.datetime.now(
                                        datetime.timezone.utc
                                    ).isoformat(),
                                    "kwargs": {"token": item},
                                }
                            )
                    results.append(item)
                    yield item
            except BaseException as e:
                stacktrace = traceback.format_exc()
                _container_end(run_container, error=stacktrace)
                raise e
            finally:
                _PARENT_RUN_TREE.set(context_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
            if results:
                if reduce_fn:
                    try:
                        function_result = reduce_fn(results)
                    except Exception as e:
                        logger.error(e)
                        function_result = results
                else:
                    function_result = results
            else:
                function_result = None
            _container_end(run_container, outputs=function_result)

        @functools.wraps(func)
        def wrapper(
            *args: Any,
            langsmith_extra: Optional[LangSmithExtra] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            context_run = get_run_tree_context()
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
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
            except BaseException as e:
                stacktrace = traceback.format_exc()
                _container_end(run_container, error=stacktrace)
                raise e
            finally:
                _PARENT_RUN_TREE.set(context_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
            _container_end(run_container, outputs=function_result)
            return function_result

        @functools.wraps(func)
        def generator_wrapper(
            *args: Any, langsmith_extra: Optional[LangSmithExtra] = None, **kwargs: Any
        ) -> Any:
            context_run = get_run_tree_context()
            run_container = _setup_run(
                func,
                container_input=container_input,
                langsmith_extra=langsmith_extra,
                args=args,
                kwargs=kwargs,
            )
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            results: List[Any] = []
            try:
                if func_accepts_parent_run:
                    generator_result = func(
                        *args, run_tree=run_container["new_run"], **kwargs
                    )
                else:
                    # TODO: Nesting is ambiguous if a nested traceable function is only
                    # called mid-generation. Need to explicitly accept run_tree to get
                    # around this.
                    generator_result = func(*args, **kwargs)
                for item in generator_result:
                    if run_type == "llm":
                        if run_container["new_run"]:
                            run_container["new_run"].add_event(
                                {
                                    "name": "new_token",
                                    "time": datetime.datetime.now(
                                        datetime.timezone.utc
                                    ).isoformat(),
                                    "kwargs": {"token": item},
                                }
                            )
                    results.append(item)
                    try:
                        yield item
                    except GeneratorExit:
                        break
            except BaseException as e:
                stacktrace = traceback.format_exc()
                _container_end(run_container, error=stacktrace)
                raise e
            finally:
                _PARENT_RUN_TREE.set(context_run)
                _PROJECT_NAME.set(run_container["outer_project"])
                _TAGS.set(run_container["outer_tags"])
                _METADATA.set(run_container["outer_metadata"])
            if results:
                if reduce_fn:
                    try:
                        function_result = reduce_fn(results)
                    except Exception as e:
                        logger.error(e)
                        function_result = results
                else:
                    function_result = results
            else:
                function_result = None
            _container_end(run_container, outputs=function_result)

        if inspect.isasyncgenfunction(func):
            selected_wrapper: Callable = async_generator_wrapper
        elif is_async(func):
            if reduce_fn:
                selected_wrapper = async_generator_wrapper
            else:
                selected_wrapper = async_wrapper
        elif reduce_fn or inspect.isgeneratorfunction(func):
            selected_wrapper = generator_wrapper
        else:
            selected_wrapper = wrapper
        setattr(selected_wrapper, "__langsmith_traceable__", True)
        return selected_wrapper

    # If the decorator is called with no arguments, then it's being used as a
    # decorator, so we return the decorator function
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return decorator(args[0])
    # Else it's being used as a decorator factory, so we return the decorator
    return decorator


@contextlib.contextmanager
def trace(
    name: str,
    run_type: ls_client.RUN_TYPE_T = "chain",
    *,
    inputs: Optional[Dict] = None,
    extra: Optional[Dict] = None,
    project_name: Optional[str] = None,
    run_tree: Optional[run_trees.RunTree] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    **kwargs: Any,
) -> Generator[run_trees.RunTree, None, None]:
    """Context manager for creating a run tree."""
    if kwargs:
        # In case someone was passing an executor before.
        warnings.warn(
            "The `trace` context manager no longer supports the following kwargs: "
            f"{sorted(kwargs.keys())}.",
            DeprecationWarning,
        )
    outer_tags = _TAGS.get()
    outer_metadata = _METADATA.get()
    outer_project = _PROJECT_NAME.get() or utils.get_tracer_project()
    parent_run_ = get_run_tree_context() if run_tree is None else run_tree

    # Merge and set context variables
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
        raise e
    finally:
        _PARENT_RUN_TREE.set(parent_run_)
        _PROJECT_NAME.set(outer_project)
        _TAGS.set(outer_tags)
        _METADATA.set(outer_metadata)
    if new_run.end_time is None:
        # User didn't call end() on the run, so we'll do it for them
        new_run.end()
    new_run.patch()


def as_runnable(traceable_fn: Callable) -> Runnable:
    """Convert a function wrapped by the LangSmith @traceable decorator to a Runnable.

    Args:
        traceable_fn (Callable): The function wrapped by the @traceable decorator.

    Returns:
        Runnable: A Runnable object that maintains a consistent LangSmith
            tracing context.

    Raises:
        ImportError: If langchain module is not installed.
        ValueError: If the provided function is not wrapped by the @traceable decorator.

    Example:
        >>> @traceable
        ... def my_function(input_data):
        ...     # Function implementation
        ...     pass
        ...
        >>> runnable = as_runnable(my_function)
    """
    try:
        from langchain.callbacks.manager import (
            AsyncCallbackManager,
            CallbackManager,
        )
        from langchain.callbacks.tracers.langchain import LangChainTracer
        from langchain.schema.runnable import RunnableConfig, RunnableLambda
        from langchain.schema.runnable.utils import Input, Output
    except ImportError as e:
        raise ImportError(
            "as_runnable requires langchain to be installed. "
            "You can install it with `pip install langchain`."
        ) from e
    if not is_traceable_function(traceable_fn):
        try:
            fn_src = inspect.getsource(traceable_fn)
        except Exception:
            fn_src = "<source unavailable>"
        raise ValueError(
            f"as_runnable expects a function wrapped by the LangSmith"
            f" @traceable decorator. Got {traceable_fn} defined as:\n{fn_src}"
        )

    class RunnableTraceable(RunnableLambda):
        """Converts a @traceable decorated function to a Runnable.

        This helps maintain a consistent LangSmith tracing context.
        """

        def __init__(
            self,
            func: Callable,
            afunc: Optional[Callable[..., Awaitable[Output]]] = None,
        ) -> None:
            wrapped: Optional[Callable[[Input], Output]] = None
            awrapped = self._wrap_async(afunc)
            if is_async(func):
                if awrapped is not None:
                    raise TypeError(
                        "Func was provided as a coroutine function, but afunc was "
                        "also provided. If providing both, func should be a regular "
                        "function to avoid ambiguity."
                    )
                wrapped = cast(Callable[[Input], Output], self._wrap_async(func))
            elif is_traceable_function(func):
                wrapped = cast(Callable[[Input], Output], self._wrap_sync(func))
            if wrapped is None:
                raise ValueError(
                    f"{self.__class__.__name__} expects a function wrapped by"
                    " the LangSmith"
                    f" @traceable decorator. Got {func}"
                )

            super().__init__(
                wrapped,
                cast(
                    Optional[Callable[[Input], Awaitable[Output]]],
                    awrapped,
                ),
            )

        @staticmethod
        def _configure_run_tree(callback_manager: Any) -> Optional[run_trees.RunTree]:
            run_tree: Optional[run_trees.RunTree] = None
            if isinstance(callback_manager, (CallbackManager, AsyncCallbackManager)):
                lc_tracers = [
                    handler
                    for handler in callback_manager.handlers
                    if isinstance(handler, LangChainTracer)
                ]
                if lc_tracers:
                    lc_tracer = lc_tracers[0]
                    run_tree = run_trees.RunTree(
                        id=callback_manager.parent_run_id,
                        session_name=lc_tracer.project_name,
                        name="Wrapping",
                        run_type="chain",
                        inputs={},
                        tags=callback_manager.tags,
                        extra={"metadata": callback_manager.metadata},
                    )
            return run_tree

        @staticmethod
        def _wrap_sync(
            func: Callable[..., Output],
        ) -> Callable[[Input, RunnableConfig], Output]:
            """Wrap a synchronous function to make it asynchronous."""

            def wrap_traceable(inputs: dict, config: RunnableConfig) -> Any:
                run_tree = RunnableTraceable._configure_run_tree(
                    config.get("callbacks")
                )
                return func(**inputs, langsmith_extra={"run_tree": run_tree})

            return cast(Callable[[Input, RunnableConfig], Output], wrap_traceable)

        @staticmethod
        def _wrap_async(
            afunc: Optional[Callable[..., Awaitable[Output]]],
        ) -> Optional[Callable[[Input, RunnableConfig], Awaitable[Output]]]:
            """Wrap an async function to make it synchronous."""
            if afunc is None:
                return None

            if not is_traceable_function(afunc):
                raise ValueError(
                    "RunnableTraceable expects a function wrapped by the LangSmith"
                    f" @traceable decorator. Got {afunc}"
                )
            afunc_ = cast(Callable[..., Awaitable[Output]], afunc)

            async def awrap_traceable(inputs: dict, config: RunnableConfig) -> Any:
                run_tree = RunnableTraceable._configure_run_tree(
                    config.get("callbacks")
                )
                return await afunc_(**inputs, langsmith_extra={"run_tree": run_tree})

            return cast(
                Callable[[Input, RunnableConfig], Awaitable[Output]], awrap_traceable
            )

    return RunnableTraceable(traceable_fn)
