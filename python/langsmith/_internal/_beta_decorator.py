import asyncio
import contextlib
import contextvars
import functools
import warnings
from collections.abc import Iterator
from typing import Any, Callable


class LangSmithBetaWarning(UserWarning):
    """This is a warning specific to the LangSmithBeta module."""


_suppress_deprecation: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "langsmith_suppress_deprecation", default=False
)


@contextlib.contextmanager
def suppress_deprecation_warning() -> Iterator[None]:
    """Silence :func:`deprecated` warnings raised inside this block.

    Several supported APIs are implemented on top of methods that are themselves
    deprecated (for example ``evaluate()`` loads an experiment's runs via
    ``list_runs()``). Warning there would tell callers to migrate a method they
    never called, so internal call sites wrap themselves in this context manager.

    Wrap only the call to the deprecated method, never a block that runs
    caller-supplied code — a user's own deprecated calls should still warn. For
    generator functions this is enough: ``deprecated()`` warns when the generator
    is created, not when it is iterated, so iteration may happen outside the block.
    """
    token = _suppress_deprecation.set(True)
    try:
        yield
    finally:
        _suppress_deprecation.reset(token)


def _warn_deprecated(message: str) -> None:
    if not _suppress_deprecation.get():
        warnings.warn(message, DeprecationWarning, stacklevel=3)


@functools.lru_cache(maxsize=100)
def _warn_once(message: str, stacklevel: int = 2) -> None:
    warnings.warn(message, LangSmithBetaWarning, stacklevel=stacklevel)


def warn_beta(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _warn_once(f"Function {func.__name__} is in beta.", stacklevel=3)
        return func(*args, **kwargs)

    return wrapper


def deprecated(message: str) -> Callable:
    """Emit DeprecationWarning when the decorated callable is called.

    Works for regular functions, generator functions, async coroutines, and async
    generator functions. The warning always fires at call time, not at iteration time.

    No warning is emitted inside :func:`suppress_deprecation_warning`, which internal
    callers use so that supported APIs don't warn about methods the caller never used.
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _warn_deprecated(message)
                return await func(*args, **kwargs)

            return async_wrapper
        else:
            # Handles regular functions, generator functions, and async generator
            # functions. Calling func() returns the iterator/generator object without
            # executing the body, so the warning fires at call time in all cases.
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _warn_deprecated(message)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
