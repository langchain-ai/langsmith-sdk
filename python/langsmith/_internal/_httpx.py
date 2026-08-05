"""Select the installed HTTPX-compatible backend."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx2 as httpx
    from httpx2 import (
        URL,
        AsyncBaseTransport,
        BaseTransport,
        Proxy,
        Response,
        Timeout,
    )
    from httpx2._config import DEFAULT_TIMEOUT_CONFIG
else:
    try:
        import httpx2 as httpx
        from httpx2 import (
            URL,
            AsyncBaseTransport,
            BaseTransport,
            Proxy,
            Response,
            Timeout,
        )
        from httpx2._config import DEFAULT_TIMEOUT_CONFIG
    except ModuleNotFoundError:
        import httpx
        from httpx import (
            URL,
            AsyncBaseTransport,
            BaseTransport,
            Proxy,
            Response,
            Timeout,
        )
        from httpx._config import DEFAULT_TIMEOUT_CONFIG

__all__ = [
    "AsyncBaseTransport",
    "BaseTransport",
    "DEFAULT_TIMEOUT_CONFIG",
    "Proxy",
    "Response",
    "Timeout",
    "URL",
    "httpx",
]
