"""WebSocket-based command execution for long-running commands."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable, Optional

from langsmith.sandbox._exceptions import (
    CommandTimeoutError,
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)


def _ensure_websockets():
    """Import websockets or raise a clear error."""
    try:
        from websockets.exceptions import ConnectionClosed, InvalidStatus
        from websockets.sync.client import connect as ws_connect

        return ws_connect, ConnectionClosed, InvalidStatus
    except ImportError:
        raise ImportError(
            "WebSocket-based execution requires the 'websockets' package. "
            "Install it with: pip install 'langsmith[sandbox]'"
        ) from None


def _ensure_websockets_async():
    """Import async websockets or raise a clear error."""
    try:
        from websockets.asyncio.client import connect as ws_connect_async
        from websockets.exceptions import ConnectionClosed, InvalidStatus

        return ws_connect_async, ConnectionClosed, InvalidStatus
    except ImportError:
        raise ImportError(
            "WebSocket-based execution requires the 'websockets' package. "
            "Install it with: pip install 'langsmith[sandbox]'"
        ) from None


def _build_ws_url(dataplane_url: str) -> str:
    """Convert dataplane HTTP URL to WebSocket URL for /execute/ws."""
    ws_url = dataplane_url.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_url}/execute/ws"


def _build_auth_headers(api_key: Optional[str]) -> dict[str, str]:
    """Build auth headers for the WebSocket upgrade request."""
    if api_key:
        return {"X-Api-Key": api_key}
    return {}


# =============================================================================
# Stream Control
# =============================================================================


class _WSStreamControl:
    """Control interface for an active WebSocket stream.

    Created before the generator starts, bound to the WebSocket once
    the connection opens. The CommandHandle holds a reference to this
    object to send kill/input messages.

    Thread safety: websockets' sync client supports send() from one
    thread while recv() runs on another. So kill() from user code
    and iteration on a different thread are safe.
    """

    def __init__(self) -> None:
        self._ws: Any = None
        self._closed = False
        self._killed = False

    def _bind(self, ws: Any) -> None:
        """Bind to the active WebSocket. Called inside the generator."""
        self._ws = ws

    def _unbind(self) -> None:
        """Mark as closed. Called when the generator exits."""
        self._closed = True
        self._ws = None

    @property
    def killed(self) -> bool:
        """True if kill() has been called on this stream."""
        return self._killed

    def send_kill(self) -> None:
        """Send a kill message to abort the running command."""
        self._killed = True
        if self._ws and not self._closed:
            self._ws.send(json.dumps({"type": "kill"}))

    def send_input(self, data: str) -> None:
        """Send stdin data to the running command."""
        if self._ws and not self._closed:
            self._ws.send(json.dumps({"type": "input", "data": data}))


class _AsyncWSStreamControl:
    """Async equivalent of _WSStreamControl."""

    def __init__(self) -> None:
        self._ws: Any = None
        self._closed = False
        self._killed = False

    def _bind(self, ws: Any) -> None:
        self._ws = ws

    def _unbind(self) -> None:
        self._closed = True
        self._ws = None

    @property
    def killed(self) -> bool:
        return self._killed

    async def send_kill(self) -> None:
        self._killed = True
        if self._ws and not self._closed:
            await self._ws.send(json.dumps({"type": "kill"}))

    async def send_input(self, data: str) -> None:
        if self._ws and not self._closed:
            await self._ws.send(json.dumps({"type": "input", "data": data}))


# =============================================================================
# Error Handling
# =============================================================================


def _raise_for_invalid_status(exc: Exception, ws_url: str) -> None:
    """Raise a clear error when the server rejects the WebSocket upgrade.

    The most common case is HTTP 404 — the server doesn't have the
    /execute/ws endpoint, meaning it doesn't support WebSocket streaming.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 404:
        raise SandboxConnectionError(
            f"The sandbox server does not support WebSocket command execution "
            f"(endpoint {ws_url} returned 404). Ensure the server is updated "
            f"to a version that supports the /execute/ws endpoint, or use "
            f"run() without wait=False or callbacks."
        ) from exc
    # For other HTTP status codes, include the status in the message
    raise SandboxConnectionError(
        f"WebSocket upgrade rejected by server (HTTP {status}): {exc}"
    ) from exc


def _raise_from_error_msg(msg: dict, *, command_id: str = "") -> None:
    """Raise the appropriate exception from a server error message."""
    error_type = msg.get("error_type", "CommandError")
    error_msg = msg.get("error", "Unknown error")

    if error_type == "CommandTimeout":
        raise CommandTimeoutError(error_msg)
    if error_type == "CommandNotFound":
        raise SandboxOperationError(
            f"Command not found: {command_id}" if command_id else error_msg,
            operation="reconnect" if command_id else "command",
            error_type=error_type,
        )
    if error_type == "SessionExpired":
        raise SandboxOperationError(
            f"Session expired: {command_id}" if command_id else error_msg,
            operation="reconnect" if command_id else "command",
            error_type=error_type,
        )

    raise SandboxOperationError(
        error_msg,
        operation="reconnect" if command_id else "command",
        error_type=error_type,
    )


# =============================================================================
# Sync Stream Functions
# =============================================================================


def run_ws_stream(
    dataplane_url: str,
    api_key: Optional[str],
    command: str,
    *,
    timeout: int = 60,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[str] = None,
    shell: str = "/bin/bash",
    on_stdout: Optional[Callable[[str], Any]] = None,
    on_stderr: Optional[Callable[[str], Any]] = None,
) -> tuple[Iterator[dict], _WSStreamControl]:
    """Execute a command over WebSocket, yielding raw message dicts.

    Returns a tuple of (message_iterator, control). The control object
    provides send_kill() and send_input() methods for the CommandHandle.

    The iterator yields dicts with a "type" field:
    - {"type": "started", "command_id": "...", "pid": N}
    - {"type": "stdout", "data": "...", "offset": N}
    - {"type": "stderr", "data": "...", "offset": N}
    - {"type": "exit", "exit_code": N}

    If on_stdout/on_stderr callbacks are provided, they are invoked as
    data arrives in addition to yielding the messages.
    """
    ws_connect, ConnectionClosed, InvalidStatus = _ensure_websockets()
    ws_url = _build_ws_url(dataplane_url)
    headers = _build_auth_headers(api_key)
    control = _WSStreamControl()

    def _stream() -> Iterator[dict]:
        try:
            with ws_connect(
                ws_url,
                additional_headers=headers,
                open_timeout=30,
                close_timeout=10,
                ping_interval=30,
                ping_timeout=60,
            ) as ws:
                control._bind(ws)

                # Send execute request
                ws.send(
                    json.dumps(
                        {
                            "type": "execute",
                            "command": command,
                            "timeout": timeout,
                            "shell": shell,
                            **({"env": env} if env else {}),
                            **({"cwd": cwd} if cwd else {}),
                        }
                    )
                )

                # Read messages until exit or error
                for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type")

                    if msg_type == "started":
                        yield msg

                    elif msg_type == "stdout":
                        if on_stdout:
                            on_stdout(msg["data"])
                        yield msg

                    elif msg_type == "stderr":
                        if on_stderr:
                            on_stderr(msg["data"])
                        yield msg

                    elif msg_type == "exit":
                        yield msg
                        return

                    elif msg_type == "error":
                        _raise_from_error_msg(msg)

        except InvalidStatus as e:
            _raise_for_invalid_status(e, ws_url)
        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        except OSError as e:
            raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e
        finally:
            control._unbind()

    return _stream(), control


def reconnect_ws_stream(
    dataplane_url: str,
    api_key: Optional[str],
    command_id: str,
    *,
    stdout_offset: int = 0,
    stderr_offset: int = 0,
) -> tuple[Iterator[dict], _WSStreamControl]:
    """Reconnect to an existing command over WebSocket.

    Returns a tuple of (message_iterator, control), same as run_ws_stream.
    The iterator yields stdout, stderr, exit, and error messages.
    No 'started' message is sent on reconnection.

    With the ring buffer reader server model, there is no replay/live
    phase distinction and no deduplication needed. The server reads from
    its ring buffer starting at the requested offsets and streams output
    from there. If the requested offset is older than the buffer's
    earliest data, the server sends from the earliest available offset.
    """
    ws_connect, ConnectionClosed, InvalidStatus = _ensure_websockets()
    ws_url = _build_ws_url(dataplane_url)
    headers = _build_auth_headers(api_key)
    control = _WSStreamControl()

    def _stream() -> Iterator[dict]:
        try:
            with ws_connect(
                ws_url,
                additional_headers=headers,
                open_timeout=30,
                close_timeout=10,
                ping_interval=30,
                ping_timeout=60,
            ) as ws:
                control._bind(ws)

                # Send reconnect request
                ws.send(
                    json.dumps(
                        {
                            "type": "reconnect",
                            "command_id": command_id,
                            "stdout_offset": stdout_offset,
                            "stderr_offset": stderr_offset,
                        }
                    )
                )

                # Read messages until exit or error
                for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type")

                    if msg_type in ("stdout", "stderr"):
                        yield msg

                    elif msg_type == "exit":
                        yield msg
                        return

                    elif msg_type == "error":
                        _raise_from_error_msg(msg, command_id=command_id)

        except InvalidStatus as e:
            _raise_for_invalid_status(e, ws_url)
        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        except OSError as e:
            raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e
        finally:
            control._unbind()

    return _stream(), control


# =============================================================================
# Async Stream Functions
# =============================================================================


async def run_ws_stream_async(
    dataplane_url: str,
    api_key: Optional[str],
    command: str,
    *,
    timeout: int = 60,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[str] = None,
    shell: str = "/bin/bash",
    on_stdout: Optional[Callable[[str], Any]] = None,
    on_stderr: Optional[Callable[[str], Any]] = None,
) -> tuple[AsyncIterator[dict], _AsyncWSStreamControl]:
    """Async equivalent of run_ws_stream.

    Returns (async_message_iterator, async_control).
    """
    ws_connect_async, ConnectionClosed, InvalidStatus = _ensure_websockets_async()
    ws_url = _build_ws_url(dataplane_url)
    headers = _build_auth_headers(api_key)
    control = _AsyncWSStreamControl()

    async def _stream() -> AsyncIterator[dict]:
        try:
            async with ws_connect_async(
                ws_url,
                additional_headers=headers,
                open_timeout=30,
                close_timeout=10,
                ping_interval=30,
                ping_timeout=60,
            ) as ws:
                control._bind(ws)

                await ws.send(
                    json.dumps(
                        {
                            "type": "execute",
                            "command": command,
                            "timeout": timeout,
                            "shell": shell,
                            **({"env": env} if env else {}),
                            **({"cwd": cwd} if cwd else {}),
                        }
                    )
                )

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type")

                    if msg_type == "started":
                        yield msg
                    elif msg_type == "stdout":
                        if on_stdout:
                            on_stdout(msg["data"])
                        yield msg
                    elif msg_type == "stderr":
                        if on_stderr:
                            on_stderr(msg["data"])
                        yield msg
                    elif msg_type == "exit":
                        yield msg
                        return
                    elif msg_type == "error":
                        _raise_from_error_msg(msg)

        except InvalidStatus as e:
            _raise_for_invalid_status(e, ws_url)
        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        except OSError as e:
            raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e
        finally:
            control._unbind()

    return _stream(), control


async def reconnect_ws_stream_async(
    dataplane_url: str,
    api_key: Optional[str],
    command_id: str,
    *,
    stdout_offset: int = 0,
    stderr_offset: int = 0,
) -> tuple[AsyncIterator[dict], _AsyncWSStreamControl]:
    """Async equivalent of reconnect_ws_stream."""
    ws_connect_async, ConnectionClosed, InvalidStatus = _ensure_websockets_async()
    ws_url = _build_ws_url(dataplane_url)
    headers = _build_auth_headers(api_key)
    control = _AsyncWSStreamControl()

    async def _stream() -> AsyncIterator[dict]:
        try:
            async with ws_connect_async(
                ws_url,
                additional_headers=headers,
                open_timeout=30,
                close_timeout=10,
                ping_interval=30,
                ping_timeout=60,
            ) as ws:
                control._bind(ws)

                await ws.send(
                    json.dumps(
                        {
                            "type": "reconnect",
                            "command_id": command_id,
                            "stdout_offset": stdout_offset,
                            "stderr_offset": stderr_offset,
                        }
                    )
                )

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("type")

                    if msg_type in ("stdout", "stderr"):
                        yield msg
                    elif msg_type == "exit":
                        yield msg
                        return
                    elif msg_type == "error":
                        _raise_from_error_msg(msg, command_id=command_id)

        except InvalidStatus as e:
            _raise_for_invalid_status(e, ws_url)
        except ConnectionClosed as e:
            if e.rcvd and e.rcvd.code == 1001:
                raise SandboxServerReloadError(
                    "Server is reloading, reconnect to resume"
                ) from e
            raise SandboxConnectionError(
                f"WebSocket connection closed unexpectedly: {e}"
            ) from e
        except OSError as e:
            raise SandboxConnectionError(f"Failed to connect to sandbox: {e}") from e
        finally:
            control._unbind()

    return _stream(), control
