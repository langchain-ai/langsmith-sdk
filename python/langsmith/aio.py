"""Async integration hooks for runtimes with custom asyncio loops.

Most applications never need this module. It exists for frameworks that run
user code on a custom :class:`asyncio.AbstractEventLoop` whose contract
differs from the default — notably durable-execution runtimes (e.g. Temporal
workflow loops) that intentionally do not support ``run_in_executor``.

Async ``@traceable`` performs sync tracing work around the user's function
(``_setup_run``, ``_on_run_end``, ``RunTree.post``/``patch``). By default
this is dispatched via ``loop.run_in_executor(None, ...)``. When a loop has
a :data:`SyncRunner` registered, LangSmith invokes that runner instead.

The runner is keyed by the event-loop instance and held in a
:class:`weakref.WeakKeyDictionary`, so it naturally lives for the lifetime
of the loop and cannot bleed across loops in the same process — which
matters because a single process may run both a custom event loop
(workflow code) and regular asyncio loops (activities, client code) that
want different dispatch behavior.

Example — Temporal-style workflow loop::

    from langsmith.aio import set_loop_sync_runner


    async def run_inline(call):
        # Workflow threads are single-threaded and deterministic; run the
        # bound call directly rather than hopping to an executor.
        return call.func(*call.args, **call.kwargs)


    workflow_loop = WorkflowEventLoop(...)
    set_loop_sync_runner(workflow_loop, run_inline)
"""

from __future__ import annotations

import asyncio
import contextvars
import weakref
from collections.abc import Awaitable, Mapping
from typing import Any, Callable, NamedTuple, Optional

__all__ = [
    "SyncRunner",
    "TracingCall",
    "get_loop_sync_runner",
    "set_loop_sync_runner",
]


class TracingCall(NamedTuple):
    """A unit of sync tracing work that LangSmith asks the runner to execute.

    A runner almost always just calls ``call.op()`` — that matches the
    default dispatch (``context.run(func, *args, **kwargs)``) while letting
    the runner choose *where* the call runs.

    The raw ``func``/``args``/``kwargs``/``context`` fields are exposed for
    runners that need the documented raw form
    ``call.func(*call.args, **call.kwargs)``. When :func:`aio_to_thread`
    receives an explicit ``__ctx``, these fields preserve that snapshot,
    so invoking them directly still writes contextvar mutations back into
    ``call.context``. Without an explicit ``__ctx``, calling the raw form
    bypasses ``context.run`` and mutates the ambient context of the caller
    instead. The latter is only safe in strictly single-threaded runtimes
    (e.g. a Temporal workflow thread).
    """

    op: Callable[[], Any]
    """Zero-arg callable equivalent to ``context.run(func, *args, **kwargs)``.

    Prefer this over the raw fields below.
    """

    func: Callable[..., Any]
    """Callable to invoke for the raw form ``call.func(*call.args, **call.kwargs)``."""

    args: tuple[Any, ...]
    """Positional arguments for ``func`` in the raw form."""

    kwargs: Mapping[str, Any]
    """Keyword arguments for ``func``."""

    context: contextvars.Context
    """The copied ``contextvars.Context`` associated with this call."""


SyncRunner = Callable[[TracingCall], Awaitable[Any]]
"""Replacement for ``loop.run_in_executor(None, op)`` on a specific loop.

Given a :class:`TracingCall`, the runner must invoke it exactly once
(usually via ``call.op()``) and return (or raise) its result. The runner
may be invoked many times per trace (setup, teardown, and each
``RunTree.post``/``patch``), so it must be reentrant.
"""


_runners: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, SyncRunner] = (
    weakref.WeakKeyDictionary()
)


def set_loop_sync_runner(
    loop: asyncio.AbstractEventLoop,
    runner: Optional[SyncRunner],
) -> None:
    """Register ``runner`` as the sync-work dispatcher for ``loop``.

    Call this once when the loop is constructed. Pass ``None`` to
    unregister. The entry is held weakly against ``loop`` and is cleared
    automatically when the loop is garbage-collected.
    """
    if runner is None:
        _runners.pop(loop, None)
    else:
        _runners[loop] = runner


def get_loop_sync_runner(
    loop: asyncio.AbstractEventLoop,
) -> Optional[SyncRunner]:
    """Return the runner registered for ``loop``, or ``None`` if none is set."""
    return _runners.get(loop)
