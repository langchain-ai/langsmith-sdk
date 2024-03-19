import inspect
import logging
from typing import Any, Generic, TypeVar, cast

from langsmith.run_helpers import traceable

logger = logging.getLogger(__name__)


def _get_module_path(module_class: type) -> str:
    """Get the full module path of a given class.

    :param module_class: The class to get the module path for.
    :type module_class: type
    :return: The module path
    :rtype: str
    """
    return (
        getattr(module_class, "__module__", "")
        or "" + "." + getattr(module_class, "__name__", "")
        or ""
    ).strip(".")


T = TypeVar("T")


class Proxy(Generic[T]):
    __slots__ = ["_ls_obj", "__weakref__"]

    def __init__(self, obj: T):
        object.__setattr__(self, "_ls_obj", obj)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_ls_obj"), name)
        return self.__class__(attr)

    def __setattr__(self, name, value):
        setattr(self._ls_obj, name, value)

    def __delattr__(self, name):
        delattr(self._ls_obj, name)

    def __call__(self, *args, **kwargs):
        function_object = object.__getattribute__(self, "_ls_obj")
        if inspect.isclass(function_object):
            # Call to a constructor. Just reflect
            return self.__class__(
                function_object(*args, **kwargs),
            )
        run_name = _get_module_path(function_object)
        return traceable(name=run_name, run_type="llm")(function_object)(
            *args, **kwargs
        )

    def __repr__(self) -> str:
        return repr(object.__getattribute__(self, "_ls_obj"))

    def __getattribute__(self, __name: str) -> Any:
        if __name.startswith("__") and __name.endswith("__"):
            return object.__getattribute__(self, __name)
        return super().__getattribute__(__name)


def wrap_sdk(client: T) -> T:
    """Wrap a client to make it traceable.

    :param client: The client to wrap.
    :type client: T
    :return: The wrapped client.
    :rtype: T
    """
    return cast(T, Proxy(client))
