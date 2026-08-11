"""Single source of the SDK's ``User-Agent``.

The tracing client and the sandbox data-plane clients are built on different
HTTP stacks (requests and httpx), so they cannot share a session — but a server
should still see one token identifying the SDK and its version. Keeping the
token here is what stops a second stack from silently shipping without one.
"""

from __future__ import annotations


def user_agent(transport_default: str = "") -> str:
    """``User-Agent`` for an outbound request from this SDK.

    ``transport_default`` is appended rather than replaced, so the underlying
    stack's own agent (``python-httpx/x.y.z``, ``Python/3.x websockets/x.y``)
    stays visible alongside ours.
    """
    import langsmith

    agent = f"langsmith-py/{langsmith.__version__}"
    return f"{agent} {transport_default}" if transport_default else agent
