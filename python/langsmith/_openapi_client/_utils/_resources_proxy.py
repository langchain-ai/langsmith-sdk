from __future__ import annotations

from typing import Any
from typing_extensions import override

from ._proxy import LazyProxy


class ResourcesProxy(LazyProxy[Any]):
    """A proxy for the `langsmith._openapi_client.resources` module.

    This is used so that we can lazily import `langsmith._openapi_client.resources` only when
    needed *and* so that users can just import `langsmith._openapi_client` and reference `langsmith._openapi_client.resources`
    """

    @override
    def __load__(self) -> Any:
        import importlib

        mod = importlib.import_module("langsmith._openapi_client.resources")
        return mod


resources = ResourcesProxy().__as_proxied__()
