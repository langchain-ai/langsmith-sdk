"""WebSocket plumbing for interactive PTY sessions."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, Optional

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._ws_execute import (
    _build_auth_headers,
    _ensure_websockets,
    _ensure_websockets_async,
    _raise_for_invalid_status,
)


def _build_session_ws_url(dataplane_url: str, session_id: str) -> str:
    """Convert dataplane HTTP URL to wss://.../sessions/{id}/ws."""
    ws_url = dataplane_url.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_url}/sessions/{session_id}/ws"


# =============================================================================
# Session WS Control (sync)
# =============================================================================


class _SessionWSControl:
    """Send input/resize over the session WS.

    Unlike _WSStreamControl, the WS is opened eagerly and owned by the
    control object.  disconnect() closes it; the output iterator just
    reads from the already-open connection.
    """

    def __init__(self) -> None:
        self._ws: Any = None
        self._closed = False

    def _bind(self, ws: Any) -> None:
        self._ws = ws

    def _unbind(self) -> None:
        self._closed = True
        self._ws = None

    def disconnect(self) -> None:
        """Close the underlying WebSocket."""
        if self._ws and not self._closed:
            try:
                self._ws.close()
            except Exception:
                pass
        self._unbind()

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed

    def send_input(self, data: str) -> None:
        """Send input to the session PTY. Data is base64-encoded."""
        if self._ws and not self._closed:
            encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
            self._ws.send(json.dumps({"type": "input", "data": encoded}))

    def send_resize(self, cols: int, rows: int) -> None:
        """Send a resize message to the session PTY."""
        if self._ws and not self._closed:
            self._ws.send(json.dumps({"type": "resize", "cols": cols, "rows": rows}))


# =============================================================================
# Session WS Control (async)
# =============================================================================


class _AsyncSessionWSControl:
    """Async equivalent of _SessionWSControl."""

    def __init__(self) -> None:
        self._ws: Any = None
        self._closed = False

    def _bind(self, ws: Any) -> None:
        self._ws = ws

    def _unbind(self) -> None:
        self._closed = True
        self._ws = None

    async def disconnect(self) -> None:
        """Close the underlying WebSocket."""
        if self._ws and not self._closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._unbind()

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._closed

    async def send_input(self, data: str) -> None:
        """Send input to the session PTY. Data is base64-encoded."""
        if self._ws and not self._closed:
            encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
            await self._ws.send(json.dumps({"type": "input", "data": encoded}))

    async def send_resize(self, cols: int, rows: int) -> None:
        """Send a resize message to the session PTY."""
        if self._ws and not self._closed:
            await self._ws.send(
                json.dumps({"type": "resize", "cols": cols, "rows": rows})
            )


# =============================================================================
# Sync connect
# =============================================================================


def connect_session_ws(
    dataplane_url: str,
    api_key: Optional[str],
    session_id: str,
) -> tuple[Iterator[str], _SessionWSControl]:
    """Open a WS to /sessions/{id}/ws eagerly.

    Returns (output_iterator, control).  The WS is opened immediately
    and bound to the control, so send_input()/send_resize() work right
    away.  The iterator yields decoded PTY output strings.
    """
    ws_connect, ConnectionClosed, InvalidStatus = _ensure_websockets()
    ws_url = _build_session_ws_url(dataplane_url, session_id)
    headers = _build_auth_headers(api_key)
    control = _SessionWSControl()

    # Open the WS eagerly so the control is usable immediately.
    try:
        ws = ws_connect(
            ws_url,
            additional_headers=headers,
            open_timeout=30,
            close_timeout=10,
            ping_interval=30,
            ping_timeout=60,
        )
        control._bind(ws)
    except InvalidStatus as e:
        _raise_for_invalid_status(e, ws_url)
    except OSError as e:
        raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e

    def _stream() -> Iterator[str]:
        try:
            for raw_msg in ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "output":
                    data_b64 = msg.get("data", "")
                    yield base64.b64decode(data_b64).decode(
                        "utf-8", errors="replace"
                    )

                elif msg_type == "error":
                    raise SandboxOperationError(
                        msg.get("data", "Unknown session error"),
                        operation="session",
                    )

        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        finally:
            control._unbind()

    return _stream(), control


# =============================================================================
# Async connect
# =============================================================================


async def connect_session_ws_async(
    dataplane_url: str,
    api_key: Optional[str],
    session_id: str,
) -> tuple[AsyncIterator[str], _AsyncSessionWSControl]:
    """Async equivalent of connect_session_ws.

    Opens the WS eagerly so the control is usable immediately.
    """
    ws_connect_async, ConnectionClosed, InvalidStatus = _ensure_websockets_async()
    ws_url = _build_session_ws_url(dataplane_url, session_id)
    headers = _build_auth_headers(api_key)
    control = _AsyncSessionWSControl()

    # Open the WS eagerly.
    try:
        ws = await ws_connect_async(
            ws_url,
            additional_headers=headers,
            open_timeout=30,
            close_timeout=10,
            ping_interval=30,
            ping_timeout=60,
        )
        control._bind(ws)
    except InvalidStatus as e:
        _raise_for_invalid_status(e, ws_url)
    except OSError as e:
        raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e

    async def _stream() -> AsyncIterator[str]:
        try:
            async for raw_msg in ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                if msg_type == "output":
                    data_b64 = msg.get("data", "")
                    yield base64.b64decode(data_b64).decode(
                        "utf-8", errors="replace"
                    )

                elif msg_type == "error":
                    raise SandboxOperationError(
                        msg.get("data", "Unknown session error"),
                        operation="session",
                    )

        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        finally:
            control._unbind()

    return _stream(), control
