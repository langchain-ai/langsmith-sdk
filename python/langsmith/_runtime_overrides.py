"""Runtime overrides for LangSmith.

This module provides hooks to override LangSmith's default runtime behavior,
primarily for environments with constrained async runtimes (e.g., Temporal).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from collections.abc import Awaitable


AioToThread = Callable[
    ...,  # (ctx: contextvars.Context, func, /, *args, **kwargs)
    "Awaitable[Any]",
]


class RuntimeOverrides:
    """Overrides for LangSmith runtime behavior.

    This class allows overriding default async implementations for environments
    that don't support certain asyncio features (e.g., Temporal doesn't support
    ``run_in_executor``).

    Example:
        import langsmith
        import contextvars


        async def my_aio_to_thread(
            default_aio_to_thread, ctx, func, /, *args, **kwargs
        ):
            # Custom implementation
            return ctx.run(func, *args, **kwargs)


        langsmith.set_runtime_overrides(aio_to_thread=my_aio_to_thread)

        # Reset to defaults
        langsmith.set_runtime_overrides()
    """

    __slots__ = ("aio_to_thread",)

    def __init__(
        self,
        aio_to_thread: Optional[AioToThread] = None,
    ):
        """Initialize runtime overrides.

        Args:
            aio_to_thread: Custom async-to-thread implementation, with signature
                ``async def (default_aio_to_thread, ctx, func, /, *args, **kwargs)``.
                ``default_aio_to_thread`` is LangSmith's default implementation, which
                the override can call to fall back to default behavior (e.g., when
                outside a constrained runtime context). ``ctx`` is the
                ``contextvars.Context`` LangSmith wants ``func`` to run inside;
                tracing state will be read back from this Context after the call.
                Override for runtimes like Temporal that don't support
                ``asyncio.run_in_executor``.
        """
        self.aio_to_thread = aio_to_thread


_runtime_overrides = RuntimeOverrides()


def set_runtime_overrides(
    aio_to_thread: Optional[AioToThread] = None,
) -> None:
    """Set LangSmith runtime overrides.

    This allows customizing LangSmith's async runtime behavior for environments
    with constrained async runtimes (e.g., Temporal, which doesn't support
    ``run_in_executor``).

    Args:
        aio_to_thread: Custom async function to run sync functions
            asynchronously. Should have signature:
            ``async def aio_to_thread(
                default_aio_to_thread, ctx, func, /, *args, **kwargs
            )``.
            ``default_aio_to_thread`` is LangSmith's default implementation, which
            the override can call to fall back to default behavior. The
            implementation must invoke ``func`` inside ``ctx`` (e.g.
            ``ctx.run(func, *args, **kwargs)``) so that LangSmith's tracing state,
            which is read back from ``ctx`` after the call, is visible to downstream
            code. Pass ``None`` to use the default implementation.

    Example:
        For Temporal or similar runtimes:

        ```python
        import langsmith


        async def temporal_aio_to_thread(
            default_aio_to_thread, ctx, func, /, *args, **kwargs
        ):
            # Use the default implementation when not in a workflow
            if not temporalio.workflow.in_workflow():
                return await default_aio_to_thread(ctx, func, *args, **kwargs)
            with temporalio.workflow.unsafe.sandbox_unrestricted():
                return ctx.run(func, *args, **kwargs)


        langsmith.set_runtime_overrides(aio_to_thread=temporal_aio_to_thread)
        ```

        Reset to defaults:

        ```python
        langsmith.set_runtime_overrides()
        ```
    """
    global _runtime_overrides
    _runtime_overrides = RuntimeOverrides(aio_to_thread=aio_to_thread)


def get_runtime_overrides() -> RuntimeOverrides:
    """Get the current runtime overrides."""
    return _runtime_overrides


def _aio_to_thread_override_active() -> bool:
    """Return True iff an ``aio_to_thread`` override is currently installed.

    Callers use this to select a loop-behavior-independent path for
    re-entering a LangSmith-mutated Context (the explicit
    ``tracing_context(**get_tracing_context(ctx))`` fallback), rather than
    relying on ``asyncio.create_task(coro, context=ctx)`` which some custom
    event loops silently ignore.
    """
    return _runtime_overrides.aio_to_thread is not None
