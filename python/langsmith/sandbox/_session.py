"""Sync interactive PTY session."""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

import httpx

from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._helpers import handle_sandbox_http_error
from langsmith.sandbox._ws_session import _SessionWSControl, connect_session_ws

if TYPE_CHECKING:
    from langsmith.sandbox._sandbox import Sandbox


@dataclass
class SessionInfo:
    """Metadata about a PTY session."""

    id: str
    shell: str
    workdir: str
    created_at: Optional[str] = None
    last_access: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionInfo:
        return cls(
            id=data["id"],
            shell=data.get("shell", ""),
            workdir=data.get("workdir", ""),
            created_at=data.get("created_at"),
            last_access=data.get("last_access"),
        )


class Session:
    """Interactive PTY session. Sync version.

    Wraps the daemon's Sessions API, providing a persistent interactive
    shell with real terminal emulation and resize support.

    Example::

        with sandbox.create_session() as session:
            session.send_input("echo hello\\n")
            for output in session:
                print(output, end="")
    """

    MAX_AUTO_RECONNECTS = 5

    def __init__(
        self,
        session_id: str,
        sandbox: Sandbox,
        *,
        shell: str = "/bin/sh",
        workdir: str = "",
    ) -> None:
        self._session_id = session_id
        self._sandbox = sandbox
        self._shell = shell
        self._workdir = workdir
        self._control: Optional[_SessionWSControl] = None
        self._stream: Optional[Iterator[str]] = None

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def connected(self) -> bool:
        return self._control is not None and self._control.connected

    def connect(self) -> None:
        """Open (or reopen) the WebSocket to this session."""
        dataplane_url = self._sandbox._require_dataplane_url()
        api_key = self._sandbox._client._api_key

        stream, control = connect_session_ws(
            dataplane_url, api_key, self._session_id
        )
        self._stream = stream
        self._control = control

    def disconnect(self) -> None:
        """Close the WebSocket. The server-side session persists."""
        if self._control is not None:
            self._control.disconnect()
        self._control = None
        self._stream = None

    def send_input(self, data: str) -> None:
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
        self._control.send_input(data)

    def resize(self, cols: int, rows: int) -> None:
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
        self._control.send_resize(cols, rows)

    def __iter__(self) -> Iterator[str]:
        """Yield PTY output strings with auto-reconnect on connection errors."""
        reconnect_count = 0

        while True:
            try:
                if self._stream is None:
                    return
                for chunk in self._stream:
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
                self.connect()
            except SandboxConnectionError:
                reconnect_count += 1
                if reconnect_count > self.MAX_AUTO_RECONNECTS:
                    raise SandboxConnectionError(
                        f"Session reconnect failed after {self.MAX_AUTO_RECONNECTS} "
                        f"attempts, giving up"
                    )
                time.sleep(0.5 * reconnect_count)
                self.connect()

    def close(self) -> None:
        """Disconnect and delete the server-side session."""
        self.disconnect()

        dataplane_url = self._sandbox._require_dataplane_url()
        url = f"{dataplane_url}/sessions/{self._session_id}"
        try:
            response = self._sandbox._client._http.delete(url, timeout=30)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            handle_sandbox_http_error(e)

    def __enter__(self) -> Session:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        try:
            self.close()
        except Exception:
            pass
