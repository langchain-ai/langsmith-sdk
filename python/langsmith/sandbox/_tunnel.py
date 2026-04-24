"""TCP tunnel for accessing services running inside sandboxes.

Establishes a WebSocket connection to the daemon's ``/tunnel`` endpoint,
runs a yamux multiplexing session on top, and forwards local TCP connections
through yamux streams to the target port inside the sandbox.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import threading
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

from langsmith.sandbox._helpers import merge_headers

if TYPE_CHECKING:
    from langsmith.sandbox._yamux import YamuxSession, YamuxStream

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunnel connect-header protocol (layered on top of yamux streams)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 0x01

STATUS_OK = 0x00
STATUS_PORT_NOT_ALLOWED = 0x01
STATUS_DIAL_FAILED = 0x02
STATUS_UNSUPPORTED_VERSION = 0x03

_CONNECT_HEADER_FMT = ">BH"  # version(1) + port(2, big-endian)


def _write_connect_header(stream: YamuxStream, port: int) -> None:
    """Write the 3-byte connect header on a freshly opened yamux stream."""
    stream.write(struct.pack(_CONNECT_HEADER_FMT, PROTOCOL_VERSION, port))


def _read_status(stream: YamuxStream) -> int:
    """Read the 1-byte status response from the daemon."""
    data = stream.read(1)
    if not data:
        raise ConnectionError("tunnel: connection closed before status")
    return data[0]


# ---------------------------------------------------------------------------
# WebSocket adapter
# ---------------------------------------------------------------------------


class _WSAdapter:
    """Adapts the ``websockets`` message API to a byte-stream interface.

    yamux requires a plain read/write/close byte stream.  WebSocket is
    message-based, so this adapter buffers partially consumed messages on
    reads and sends one binary message per write.
    """

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._buf = bytearray()
        self._write_lock = threading.Lock()

    def read(self, n: int) -> bytes:
        while len(self._buf) < n:
            msg = self._ws.recv()
            if isinstance(msg, str):
                msg = msg.encode()
            self._buf.extend(msg)

        result = bytes(self._buf[:n])
        del self._buf[:n]
        return result

    def write(self, data: bytes) -> int:
        with self._write_lock:
            self._ws.send(data)
        return len(data)

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Bridge: bidirectional copy between yamux stream and TCP socket
# ---------------------------------------------------------------------------

_BRIDGE_BUF_SIZE = 16384


def _bridge(stream: YamuxStream, tcp_conn: socket.socket) -> None:
    """Copy data bidirectionally until one side closes or errors."""
    done = threading.Event()

    def _stream_to_tcp() -> None:
        try:
            while True:
                data = stream.read(_BRIDGE_BUF_SIZE)
                if not data:
                    break
                tcp_conn.sendall(data)
        except Exception:
            pass
        finally:
            done.set()

    def _tcp_to_stream() -> None:
        try:
            while True:
                data = tcp_conn.recv(_BRIDGE_BUF_SIZE)
                if not data:
                    break
                stream.write(data)
        except Exception:
            pass
        finally:
            done.set()

    t1 = threading.Thread(target=_stream_to_tcp, daemon=True)
    t2 = threading.Thread(target=_tcp_to_stream, daemon=True)
    t1.start()
    t2.start()

    done.wait()

    try:
        stream.close()
    except Exception:
        pass
    try:
        tcp_conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        tcp_conn.close()
    except OSError:
        pass

    t1.join(timeout=5)
    t2.join(timeout=5)


# ---------------------------------------------------------------------------
# Tunnel
# ---------------------------------------------------------------------------


def _ensure_websockets():
    """Import websockets sync client or raise a clear error."""
    try:
        from websockets.sync.client import connect as ws_connect

        return ws_connect
    except ImportError:
        raise ImportError(
            "TCP tunnel requires the 'websockets' package. "
            "Install it with: pip install 'langsmith[sandbox]'"
        ) from None


class Tunnel:
    """TCP tunnel to a port inside a sandbox.

    Opens a local TCP listener and forwards each accepted connection through
    a yamux-multiplexed WebSocket to the daemon, which dials the target port
    inside the sandbox.

    Typically used as a context manager::

        with sandbox.tunnel(remote_port=5432) as t:
            conn = psycopg2.connect(host="127.0.0.1", port=t.local_port)

    Or with explicit lifecycle::

        t = sandbox.tunnel(remote_port=5432)
        # ... use tunnel ...
        t.close()
    """

    _BACKOFF_BASE = 0.5
    _BACKOFF_MAX = 8.0

    def __init__(
        self,
        dataplane_url: str,
        api_key: Optional[str],
        remote_port: int,
        *,
        local_port: int = 0,
        max_reconnects: int = 3,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._dataplane_url = dataplane_url
        self._api_key = api_key
        self._headers = headers
        self._remote_port = remote_port
        self._requested_local_port = local_port or remote_port
        self._local_port = self._requested_local_port
        self._max_reconnects = max_reconnects

        self._ws: object = None
        self._yamux: Optional[YamuxSession] = None
        self._server_socket: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._reconnect_lock = threading.Lock()
        self._closed = False
        self._started = False

    @property
    def local_port(self) -> int:
        """Local port the tunnel is listening on."""
        return self._local_port

    @property
    def remote_port(self) -> int:
        """Port inside the sandbox that the tunnel connects to."""
        return self._remote_port

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> Tunnel:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- Lifecycle ----------------------------------------------------------

    def _start(self) -> None:
        if self._started:
            return
        self._started = True

        try:
            self._do_start()
        except Exception:
            self.close()
            raise

    def _do_start(self) -> None:
        self._connect()

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Check if another process is actively listening on this port.
        # SO_REUSEADDR lets us rebind over TIME_WAIT, but we don't want to
        # silently steal a port from a running service.
        port = self._requested_local_port
        if port != 0:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.settimeout(0.5)
                probe.connect(("127.0.0.1", port))
                probe.close()
                raise OSError(
                    f"Port {port} is already in use by another service. "
                    f"Choose a different local_port."
                )
            except ConnectionRefusedError:
                pass  # nothing listening — safe to bind
            except OSError as e:
                if "Connection refused" in str(e):
                    pass  # same as above, different OS error message
                elif "already in use" in str(e).lower():
                    raise
                else:
                    pass  # TIME_WAIT or other transient state — safe to bind
            finally:
                try:
                    probe.close()
                except OSError:
                    pass

        self._server_socket.bind(("127.0.0.1", self._requested_local_port))
        self._server_socket.listen(128)
        self._local_port = self._server_socket.getsockname()[1]

        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="tunnel-accept"
        )
        self._accept_thread.start()

    def _connect(self) -> None:
        """Establish (or re-establish) the WebSocket + yamux session."""
        from langsmith.sandbox._yamux import YamuxSession

        old_yamux = self._yamux
        if old_yamux:
            try:
                old_yamux.close()
            except Exception:
                pass

        ws_connect = _ensure_websockets()
        ws_url = self._build_ws_url()
        headers = merge_headers(
            {"X-Api-Key": self._api_key} if self._api_key else None,
            self._headers,
        )

        self._ws = ws_connect(
            ws_url,
            additional_headers=headers,
            open_timeout=15,
            close_timeout=5,
            ping_interval=None,  # yamux handles keepalive
        )

        adapter = _WSAdapter(self._ws)
        self._yamux = YamuxSession(adapter)

    def _ensure_session(self) -> YamuxSession:
        """Return a live yamux session, reconnecting if needed."""
        from langsmith.sandbox._exceptions import TunnelError

        if self._yamux and not self._yamux.is_closed:
            return self._yamux

        with self._reconnect_lock:
            if self._yamux and not self._yamux.is_closed:
                return self._yamux

            last_err: Optional[Exception] = None
            for attempt in range(self._max_reconnects):
                try:
                    self._connect()
                    logger.debug("tunnel: reconnected (attempt %d)", attempt + 1)
                    return self._yamux  # type: ignore[return-value]
                except Exception as exc:
                    last_err = exc
                    if attempt < self._max_reconnects - 1:
                        delay = min(
                            self._BACKOFF_BASE * (2**attempt),
                            self._BACKOFF_MAX,
                        )
                        time.sleep(delay)

            raise TunnelError(
                f"tunnel: reconnect failed after {self._max_reconnects} attempts"
            ) from last_err

    def close(self) -> None:
        """Shut down the tunnel, closing all connections."""
        if self._closed:
            return
        self._closed = True

        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass

        if self._yamux:
            self._yamux.close()

    # -- Internal -----------------------------------------------------------

    def _accept_loop(self) -> None:
        while not self._closed:
            try:
                conn, _ = self._server_socket.accept()  # type: ignore[union-attr]
            except OSError:
                break
            threading.Thread(
                target=self._handle_conn,
                args=(conn,),
                daemon=True,
                name="tunnel-bridge",
            ).start()

    def _handle_conn(self, tcp_conn: socket.socket) -> None:
        try:
            session = self._ensure_session()
            stream = session.open_stream()
            _write_connect_header(stream, self._remote_port)
            status = _read_status(stream)

            if status == STATUS_OK:
                _bridge(stream, tcp_conn)
                return

            stream.close()
            tcp_conn.close()

            if status == STATUS_PORT_NOT_ALLOWED:
                logger.warning(
                    "tunnel: port %d not allowed by daemon",
                    self._remote_port,
                )
            elif status == STATUS_DIAL_FAILED:
                logger.warning(
                    "tunnel: nothing listening on port %d inside sandbox",
                    self._remote_port,
                )
            elif status == STATUS_UNSUPPORTED_VERSION:
                logger.warning(
                    "tunnel: protocol version mismatch (client v%d)",
                    PROTOCOL_VERSION,
                )
            else:
                logger.warning("tunnel: unknown status %d", status)

        except Exception as exc:
            logger.debug("tunnel: connection handler error: %s", exc)
            try:
                tcp_conn.close()
            except OSError:
                pass

    def _build_ws_url(self) -> str:
        url = self._dataplane_url.rstrip("/")
        url = url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{url}/tunnel"


# ---------------------------------------------------------------------------
# AsyncTunnel
# ---------------------------------------------------------------------------


class AsyncTunnel:
    """Async wrapper around :class:`Tunnel`.

    The underlying tunnel runs in background threads (TCP listener + bridges);
    async context-manager methods delegate to the sync tunnel via the event
    loop's executor.

    Usage::

        async with await sandbox.tunnel(remote_port=5432) as t:
            conn = await asyncpg.connect(host="127.0.0.1", port=t.local_port)
    """

    def __init__(
        self,
        dataplane_url: str,
        api_key: Optional[str],
        remote_port: int,
        *,
        local_port: int = 0,
        max_reconnects: int = 3,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._tunnel = Tunnel(
            dataplane_url,
            api_key,
            remote_port,
            local_port=local_port,
            max_reconnects=max_reconnects,
            headers=headers,
        )

    @property
    def local_port(self) -> int:
        return self._tunnel.local_port

    @property
    def remote_port(self) -> int:
        return self._tunnel.remote_port

    async def __aenter__(self) -> AsyncTunnel:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tunnel._start)
        return self

    async def __aexit__(self, *args: object) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tunnel.close)

    def close(self) -> None:
        """Shut down the tunnel (sync, safe to call from any context)."""
        self._tunnel.close()
