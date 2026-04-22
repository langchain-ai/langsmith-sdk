"""Runtime overrides for LangSmith.

This module provides hooks to override LangSmith's default runtime behavior,
primarily for environments with constrained async runtimes (e.g., Temporal).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from collections.abc import Awaitable


class RuntimeOverrides:
    """Overrides for LangSmith runtime behavior.

    This class allows overriding default async implementations for environments
    that don't support certain asyncio features (e.g., Temporal doesn't support
    run_in_executor).

    Example:
        import langsmith

        # For Temporal or other constrained runtimes
        async def my_aio_to_thread(func, /, *args, __ctx=None, **kwargs):
            # Custom implementation
            return await some_wrapper(func, *args, **kwargs)

        langsmith.set_runtime_overrides(aio_to_thread=my_aio_to_thread)

        # Reset to defaults
        langsmith.set_runtime_overrides()
    """

    __slots__ = ("aio_to_thread",)

    def __init__(
        self,
        aio_to_thread: Optional[Callable[..., Awaitable[Any]]] = None,
    ):
        """Initialize runtime overrides.

        Args:
            aio_to_thread: Custom async-to-thread implementation.
                Used to run sync functions asynchronously. Override for runtimes
                like Temporal that don't support asyncio.run_in_executor.
        """
        self.aio_to_thread = aio_to_thread


# Global runtime overrides instance
_runtime_overrides = RuntimeOverrides()


def set_runtime_overrides(
    aio_to_thread: Optional[Callable[..., Awaitable[Any]]] = None,
) -> None:
    """Set LangSmith runtime overrides.

    This allows customizing LangSmith's async runtime behavior for environments
    with constrained async runtimes (e.g., Temporal, which doesn't support
    run_in_executor).

    Args:
        aio_to_thread: Custom async function to run sync functions
            asynchronously. Should have signature:
            async def aio_to_thread(func, /, *args, __ctx=None, **kwargs)
            Pass None to use the default implementation.

    Example:
        For Temporal or similar runtimes:

        ```python
        import langsmith


        async def temporal_aio_to_thread(func, /, *args, __ctx=None, **kwargs):
            # Use Temporal's activity execution or similar
            return await temporal_async_wrapper(func, *args, **kwargs)


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
