"""Select the HTTPX-compatible backend used by this package.

The maintained `httpx2` fork is preferred when it is installed, with a fallback to
`httpx` so that environments that still depend on the original package keep working.
Every module in this package imports HTTPX through here so that the client, response,
transport, timeout and exception types all come from a single backend.

Type checkers resolve against `httpx`, which is this package's declared dependency —
`httpx2` is an API-compatible fork, so its annotations apply to either backend, and
pointing the `TYPE_CHECKING` branch at a package that may not be installed would make
every name re-exported here resolve to `Unknown`.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
    from httpx import (
        URL,
        Proxy,
        Client,
        Limits,
        Request,
        Timeout,
        Response,
        AsyncClient,
        BaseTransport,
        MockTransport,
        AsyncBaseTransport,
    )
    from httpx._config import (
        DEFAULT_TIMEOUT_CONFIG,  # pyright: ignore[reportPrivateImportUsage]
    )
else:
    try:
        import httpx2 as httpx
        from httpx2 import (
            URL,
            Proxy,
            Client,
            Limits,
            Request,
            Timeout,
            Response,
            AsyncClient,
            BaseTransport,
            MockTransport,
            AsyncBaseTransport,
        )
        from httpx2._config import DEFAULT_TIMEOUT_CONFIG
    except ModuleNotFoundError:
        import httpx
        from httpx import (
            URL,
            Proxy,
            Client,
            Limits,
            Request,
            Timeout,
            Response,
            AsyncClient,
            BaseTransport,
            MockTransport,
            AsyncBaseTransport,
        )
        from httpx._config import DEFAULT_TIMEOUT_CONFIG

__all__ = [
    "httpx",
    "URL",
    "Proxy",
    "Client",
    "Limits",
    "Request",
    "Timeout",
    "Response",
    "AsyncClient",
    "BaseTransport",
    "MockTransport",
    "AsyncBaseTransport",
    "DEFAULT_TIMEOUT_CONFIG",
]
