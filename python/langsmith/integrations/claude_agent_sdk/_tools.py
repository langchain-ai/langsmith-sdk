"""Tool instrumentation for Claude Agent SDK."""

import logging
import threading
from typing import Any, Callable

from langsmith.run_helpers import get_current_run_tree, trace

logger = logging.getLogger(__name__)

# Thread-local store for passing the parent run tree into tool handlers.
# Claude's async event loop by default breaks tracing.
# contextvars start empty within new anyio threads. The parent run tree is threaded
# via thread-local as a fallback when context propagation isn't available.
_thread_local = threading.local()


def set_parent_run_tree(run_tree: Any) -> None:
    """Set the parent run tree in thread-local storage."""
    _thread_local.parent_run_tree = run_tree


def clear_parent_run_tree() -> None:
    """Clear the parent run tree from thread-local storage."""
    if hasattr(_thread_local, "parent_run_tree"):
        delattr(_thread_local, "parent_run_tree")


def get_parent_run_tree() -> Any:
    """Get the parent run tree from thread-local storage."""
    return getattr(_thread_local, "parent_run_tree", None)


def instrument_sdk_mcp_tool_class(original_class: Any) -> Any:
    """Create a traced subclass of SdkMcpTool that wraps its handler."""

    class TracedSdkMcpTool(original_class):
        def __init__(
            self,
            name: Any,
            description: Any,
            input_schema: Any,
            handler: Any,
            **kw: Any,
        ):
            super().__init__(
                name,
                description,
                input_schema,
                instrument_tool_handler(handler, name),
                **kw,
            )

        # Retain generic access for SDKs using typing in __class_getitem__
        __class_getitem__ = classmethod(lambda cls, _: cls)

    # Let other wrap paths know the class already instruments handlers.
    setattr(TracedSdkMcpTool, "__ls_tool_class_wrapped__", True)

    return TracedSdkMcpTool


def instrument_tool_factory(tool_fn: Any) -> Callable[..., Any]:
    """Instrument tool() factory so resulting handlers include tracing."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        decorator = tool_fn(*args, **kwargs)
        if not callable(decorator):
            return decorator

        def traced_decorator(fn: Any) -> Any:
            tool_def = decorator(fn)
            if hasattr(tool_def, "handler"):
                # If the tool class already instruments handlers, don't wrap again.
                cls = tool_def.__class__
                if not getattr(cls, "__ls_tool_class_wrapped__", False):
                    tool_def.handler = instrument_tool_handler(
                        tool_def.handler, getattr(tool_def, "name", "unnamed_tool")
                    )
            return tool_def

        return traced_decorator

    return wrapper


def instrument_tool_handler(handler: Any, name: Any) -> Callable[..., Any]:
    """Instrument an individual tool handler to create a traced run."""
    if getattr(handler, "_ls_wrapped", False):
        return handler

    async def traced_handler(args: Any) -> Any:
        parent = get_parent_run_tree() or get_current_run_tree()
        async with trace(
            name=str(name),
            run_type="tool",
            inputs=args,
            parent=parent,
        ) as run:
            result = await handler(args)
            run.end(outputs=result)
            return result

    traced_handler._ls_wrapped = True  # type: ignore[attr-defined]
    return traced_handler
