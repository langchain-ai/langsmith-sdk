import asyncio
import functools
import warnings
from typing import Any, Callable


class LangSmithBetaWarning(UserWarning):
    """This is a warning specific to the LangSmithBeta module."""


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
    """Decorator that emits DeprecationWarning when the decorated callable is called.

    Works for regular functions, generator functions, async coroutines, and async
    generator functions. The warning always fires at call time, not at iteration time.
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                return await func(*args, **kwargs)

            return async_wrapper
        else:
            # Handles regular functions, generator functions, and async generator
            # functions. Calling func() returns the iterator/generator object without
            # executing the body, so the warning fires at call time in all cases.
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
