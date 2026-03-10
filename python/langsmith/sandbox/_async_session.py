"""Async interactive PTY session."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Optional

import httpx

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._helpers import handle_sandbox_http_error
from langsmith.sandbox._ws_session import _AsyncSessionWSControl, connect_session_ws_async

if TYPE_CHECKING:
    from langsmith.sandbox._async_sandbox import AsyncSandbox


class AsyncSession:
    """Interactive PTY session. Async version.

    Wraps the daemon's Sessions API, providing a persistent interactive
    shell with real terminal emulation and resize support.

    Example::

        async with await sandbox.create_session() as session:
            await session.send_input("echo hello\\n")
            async for output in session:
                print(output, end="")
    """

    MAX_AUTO_RECONNECTS = 5

    def __init__(
        self,
        session_id: str,
        sandbox: AsyncSandbox,
        *,
        shell: str = "/bin/sh",
        workdir: str = "",
    ) -> None:
        self._session_id = session_id
        self._sandbox = sandbox
        self._shell = shell
        self._workdir = workdir
        self._control: Optional[_AsyncSessionWSControl] = None
        self._stream: Optional[AsyncIterator[str]] = None

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def connected(self) -> bool:
        return self._control is not None and self._control.connected

    async def connect(self) -> None:
        """Open (or reopen) the WebSocket to this session."""
        dataplane_url = self._sandbox._require_dataplane_url()
        api_key = self._sandbox._client._api_key

        stream, control = await connect_session_ws_async(
            dataplane_url, api_key, self._session_id
        )
        self._stream = stream
        self._control = control

    async def disconnect(self) -> None:
        """Close the WebSocket. The server-side session persists."""
        if self._control is not None:
            await self._control.disconnect()
        self._control = None
        self._stream = None

    async def send_input(self, data: str) -> None:
        """Send input to the session PTY.

        Args:
            data: String to send (will be base64-encoded over the wire).

        Raises:
            SandboxOperationError: If not connected.
        """
        if not self.connected:
            raise SandboxOperationError(
                "Session is not connected. Call connect() first.",
                operation="session",
            )
        assert self._control is not None
        await self._control.send_input(data)

    async def resize(self, cols: int, rows: int) -> None:
        """Resize the session PTY.

        Args:
            cols: Number of columns.
            rows: Number of rows.

        Raises:
            SandboxOperationError: If not connected.
        """
        if not self.connected:
            raise SandboxOperationError(
                "Session is not connected. Call connect() first.",
                operation="session",
            )
        assert self._control is not None
        await self._control.send_resize(cols, rows)

    async def __aiter__(self) -> AsyncIterator[str]:
        """Yield PTY output strings with auto-reconnect on connection errors."""
        reconnect_count = 0

        while True:
            try:
                if self._stream is None:
                    return
                async for chunk in self._stream:
                    reconnect_count = 0  # reset on successful data
                    yield chunk
                # Stream ended normally
                return
            except SandboxServerReloadError:
                reconnect_count += 1
                if reconnect_count > self.MAX_AUTO_RECONNECTS:
                    raise SandboxConnectionError(
                        f"Session reconnect failed after {self.MAX_AUTO_RECONNECTS} "
                        f"attempts, giving up"
                    )
                # Immediate reconnect (no backoff) for server reload
                await self.connect()
            except SandboxConnectionError:
                reconnect_count += 1
                if reconnect_count > self.MAX_AUTO_RECONNECTS:
                    raise SandboxConnectionError(
                        f"Session reconnect failed after {self.MAX_AUTO_RECONNECTS} "
                        f"attempts, giving up"
                    )
                await asyncio.sleep(0.5 * reconnect_count)
                await self.connect()

    async def close(self) -> None:
        """Disconnect and delete the server-side session."""
        await self.disconnect()

        dataplane_url = self._sandbox._require_dataplane_url()
        url = f"{dataplane_url}/sessions/{self._session_id}"
        try:
            response = await self._sandbox._client._http.delete(url, timeout=30)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            handle_sandbox_http_error(e)

    async def __aenter__(self) -> AsyncSession:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        try:
            await self.close()
        except Exception:
            pass
