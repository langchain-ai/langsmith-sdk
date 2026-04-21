"""Hook for customizing how LangSmith offloads sync tracing work from async code.

Most applications never need this module. It exists for frameworks that run
user code on a custom :class:`asyncio.AbstractEventLoop` whose contract
differs from the default — notably durable-execution runtimes (e.g. Temporal
workflow loops) that intentionally do not support ``run_in_executor``.

Async ``@traceable`` performs sync tracing work around the user's function
(``_setup_run``, ``_on_run_end``, ``RunTree.post``/``patch``). By default
this is offloaded via ``loop.run_in_executor(None, ...)``. Installing a
:data:`TracingOffload` replaces that dispatch with a caller-chosen strategy
(run inline, submit to an external thread pool, etc.).

The offload is stored in a :class:`~contextvars.ContextVar`, so it scopes
to the current ``contextvars.Context`` and naturally follows coroutines/tasks
spawned from the setting frame. It does not bleed into other coroutines in
the same process — which matters because a single process may run both a
custom event loop (workflow code) and regular asyncio loops (activities,
client code) that want different dispatch behavior.

Example — Temporal-style workflow interceptor::

    from langsmith.tracing_offload import tracing_offload


    async def run_inline(call):
        # Workflow threads are single-threaded and deterministic; run the
        # bound call directly rather than hopping to an executor.
        return call.op()


    async def execute_workflow(input):
        with tracing_offload(run_inline):
            return await next_.execute_workflow(input)
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Awaitable, Mapping
from typing import Any, Callable, NamedTuple, Optional

__all__ = [
    "TracingCall",
    "TracingOffload",
    "get_tracing_offload",
    "reset_tracing_offload",
    "set_tracing_offload",
    "tracing_offload",
]


class TracingCall(NamedTuple):
    """A unit of sync tracing work that LangSmith asks the offload to execute.

    An offload almost always just calls ``call.op()`` — that matches the
    default dispatch (``context.run(func, *args, **kwargs)``) while letting
    the offload choose *where* the call runs.

    The raw ``func``/``args``/``kwargs``/``context`` fields are exposed for
    the narrow case where an offload must bypass ``context.run`` so that
    contextvar mutations performed by ``func`` remain visible to the
    ambient context of the caller. Doing so is only safe in strictly
    single-threaded runtimes (e.g. a Temporal workflow thread).
    """

    op: Callable[[], Any]
    """Zero-arg callable equivalent to ``context.run(func, *args, **kwargs)``.

    Prefer this over the raw fields below.
    """

    func: Callable[..., Any]
    """The underlying sync callable LangSmith wants to run."""

    args: tuple[Any, ...]
    """Positional arguments for ``func``."""

    kwargs: Mapping[str, Any]
    """Keyword arguments for ``func``."""

    context: contextvars.Context
    """The copied ``contextvars.Context`` associated with this call."""


TracingOffload = Callable[[TracingCall], Awaitable[Any]]
"""Strategy for offloading sync tracing work.

Given a :class:`TracingCall`, the offload must invoke it exactly once
(usually via ``call.op()``) and return (or raise) its result. The offload
may be called many times per trace (setup, teardown, and each
``RunTree.post``/``patch``), so it must be reentrant.
"""


_current: contextvars.ContextVar[Optional[TracingOffload]] = contextvars.ContextVar(
    "langsmith_tracing_offload", default=None
)


def set_tracing_offload(offload: Optional[TracingOffload]) -> contextvars.Token:
    """Install ``offload`` in the current :class:`~contextvars.Context`.

    Returns a token that should be passed to :func:`reset_tracing_offload`
    to restore the previous value. Passing ``None`` explicitly disables any
    inherited offload for the current context.
    """
    return _current.set(offload)


def reset_tracing_offload(token: contextvars.Token) -> None:
    """Restore the tracing offload to what it was before the matching ``set`` call."""
    _current.reset(token)


def get_tracing_offload() -> Optional[TracingOffload]:
    """Return the tracing offload installed in the current context, or ``None``."""
    return _current.get()


@contextlib.contextmanager
def tracing_offload(offload: TracingOffload):
    """Scope a tracing offload to a ``with`` block."""
    token = _current.set(offload)
    try:
        yield
    finally:
        _current.reset(token)
