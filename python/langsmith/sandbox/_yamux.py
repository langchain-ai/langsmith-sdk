"""Minimal yamux (Yet Another Multiplexer) client for TCP tunneling.

Implements the client side of the yamux protocol as specified at
https://github.com/hashicorp/yamux/blob/master/spec.md

Only the subset needed for tunnel client operation is implemented:
opening streams, sending/receiving data, flow control, and keepalive.
"""

from __future__ import annotations

import struct
import threading
from typing import Protocol

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

_VERSION = 0

_TYPE_DATA = 0
_TYPE_WINDOW_UPDATE = 1
_TYPE_PING = 2
_TYPE_GO_AWAY = 3

_FLAG_SYN = 0x0001
_FLAG_ACK = 0x0002
_FLAG_FIN = 0x0004
_FLAG_RST = 0x0008

_HEADER_SIZE = 12
_HEADER_FMT = ">BBHII"  # version(1), type(1), flags(2), streamID(4), length(4)

_INITIAL_WINDOW_SIZE = 256 * 1024  # 256 KB


# ---------------------------------------------------------------------------
# Byte-stream interface required by the session
# ---------------------------------------------------------------------------


class _ReadWriteCloser(Protocol):
    def read(self, n: int) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# YamuxStream
# ---------------------------------------------------------------------------


class YamuxStream:
    """A single multiplexed stream within a yamux session.

    Streams are created via :meth:`YamuxSession.open_stream` and provide
    blocking read/write/close with per-stream flow control.
    """

    def __init__(self, stream_id: int, session: YamuxSession) -> None:
        self._id = stream_id
        self._session = session

        self._recv_buf = bytearray()
        self._recv_cond = threading.Condition()
        self._recv_closed = False
        self._recv_error = False
        self._recv_window = _INITIAL_WINDOW_SIZE

        self._send_window = _INITIAL_WINDOW_SIZE
        self._send_cond = threading.Condition()
        self._send_closed = False

    @property
    def stream_id(self) -> int:
        return self._id

    def read(self, n: int) -> bytes:
        """Read up to *n* bytes, blocking until data is available.

        Returns ``b""`` on EOF (FIN received).
        Raises :class:`ConnectionResetError` on RST.
        """
        delta_to_send = 0

        with self._recv_cond:
            while not self._recv_buf and not self._recv_closed and not self._recv_error:
                self._recv_cond.wait()

            if self._recv_error and not self._recv_buf:
                raise ConnectionResetError("yamux stream reset by peer")

            if not self._recv_buf:
                return b""

            size = min(n, len(self._recv_buf))
            data = bytes(self._recv_buf[:size])
            del self._recv_buf[:size]

            consumed = _INITIAL_WINDOW_SIZE - self._recv_window
            if consumed >= _INITIAL_WINDOW_SIZE // 2:
                delta_to_send = consumed
                self._recv_window += consumed

        if delta_to_send > 0:
            try:
                self._session._send_window_update(self._id, delta_to_send)
            except Exception:
                pass

        return data

    def write(self, data: bytes) -> int:
        """Write *data*, blocking if the send window is exhausted."""
        if self._send_closed:
            raise BrokenPipeError("yamux stream closed for writing")

        offset = 0
        mv = memoryview(data)

        while offset < len(data):
            with self._send_cond:
                while self._send_window == 0 and not self._send_closed:
                    self._send_cond.wait()
                if self._send_closed:
                    raise BrokenPipeError("yamux stream closed for writing")
                chunk = min(len(data) - offset, self._send_window)
                self._send_window -= chunk

            self._session._send_data(self._id, bytes(mv[offset : offset + chunk]))
            offset += chunk

        return len(data)

    def close(self) -> None:
        """Close the stream (sends FIN to the remote end)."""
        if not self._send_closed:
            self._send_closed = True
            try:
                self._session._send_frame(_TYPE_DATA, _FLAG_FIN, self._id, 0)
            except Exception:
                pass

        with self._recv_cond:
            self._recv_closed = True
            self._recv_cond.notify_all()
        with self._send_cond:
            self._send_cond.notify_all()

    # -- Internal: called by YamuxSession._read_loop ------------------------

    def _receive_data(self, data: bytes) -> None:
        with self._recv_cond:
            self._recv_buf.extend(data)
            self._recv_window -= len(data)
            self._recv_cond.notify_all()

    def _receive_fin(self) -> None:
        with self._recv_cond:
            self._recv_closed = True
            self._recv_cond.notify_all()

    def _receive_rst(self) -> None:
        with self._recv_cond:
            self._recv_error = True
            self._recv_cond.notify_all()
        with self._send_cond:
            self._send_closed = True
            self._send_cond.notify_all()

    def _update_send_window(self, delta: int) -> None:
        with self._send_cond:
            self._send_window += delta
            self._send_cond.notify_all()


# ---------------------------------------------------------------------------
# YamuxSession
# ---------------------------------------------------------------------------


class YamuxSession:
    """Client-side yamux session over a byte-stream connection.

    The connection must implement ``read(n) -> bytes``, ``write(data) -> int``,
    and ``close() -> None``.  Typically this is a :class:`_WSAdapter` wrapping
    a WebSocket.

    Usage::

        session = YamuxSession(conn)
        stream = session.open_stream()
        stream.write(b"hello")
        data = stream.read(1024)
        stream.close()
        session.close()
    """

    def __init__(self, conn: _ReadWriteCloser) -> None:
        self._conn = conn
        self._streams: dict[int, YamuxStream] = {}
        self._next_stream_id = 1  # client uses odd IDs
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._closed = False
        self._shutdown_event = threading.Event()

        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="yamux-reader"
        )
        self._reader_thread.start()

        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop, daemon=True, name="yamux-keepalive"
        )
        self._keepalive_thread.start()

    @property
    def is_closed(self) -> bool:
        return self._closed

    def open_stream(self) -> YamuxStream:
        """Open a new multiplexed stream.

        Raises :class:`RuntimeError` if the session is closed.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("yamux session is closed")
            stream_id = self._next_stream_id
            self._next_stream_id += 2
            stream = YamuxStream(stream_id, self)
            self._streams[stream_id] = stream

        self._send_frame(_TYPE_WINDOW_UPDATE, _FLAG_SYN, stream_id, 0)
        return stream

    def close(self) -> None:
        """Close the session and all streams."""
        if self._closed:
            return
        self._closed = True
        self._shutdown_event.set()

        try:
            self._send_frame(_TYPE_GO_AWAY, 0, 0, 0)
        except Exception:
            pass

        with self._lock:
            for stream in self._streams.values():
                stream._receive_rst()

        try:
            self._conn.close()
        except Exception:
            pass

    # -- Frame I/O ----------------------------------------------------------

    def _send_frame(
        self, msg_type: int, flags: int, stream_id: int, length: int
    ) -> None:
        hdr = struct.pack(_HEADER_FMT, _VERSION, msg_type, flags, stream_id, length)
        with self._write_lock:
            self._conn.write(hdr)

    def _send_data(self, stream_id: int, data: bytes) -> None:
        hdr = struct.pack(_HEADER_FMT, _VERSION, _TYPE_DATA, 0, stream_id, len(data))
        with self._write_lock:
            self._conn.write(hdr + data)

    def _send_window_update(self, stream_id: int, delta: int) -> None:
        self._send_frame(_TYPE_WINDOW_UPDATE, 0, stream_id, delta)

    # -- Read loop ----------------------------------------------------------

    def _read_loop(self) -> None:
        try:
            while not self._closed:
                hdr_bytes = self._conn.read(_HEADER_SIZE)
                if len(hdr_bytes) < _HEADER_SIZE:
                    break

                _ver, msg_type, flags, stream_id, length = struct.unpack(
                    _HEADER_FMT, hdr_bytes
                )

                if msg_type == _TYPE_DATA:
                    self._handle_data(flags, stream_id, length)
                elif msg_type == _TYPE_WINDOW_UPDATE:
                    self._handle_window_update(flags, stream_id, length)
                elif msg_type == _TYPE_PING:
                    self._handle_ping(flags, length)
                elif msg_type == _TYPE_GO_AWAY:
                    break
        except Exception:
            pass
        finally:
            if not self._closed:
                self._closed = True
                self._shutdown_event.set()
                with self._lock:
                    for stream in self._streams.values():
                        stream._receive_rst()

    def _handle_data(self, flags: int, stream_id: int, length: int) -> None:
        payload = self._conn.read(length) if length > 0 else b""

        with self._lock:
            stream = self._streams.get(stream_id)
        if stream is None:
            return

        if payload:
            stream._receive_data(payload)
        if flags & _FLAG_FIN:
            stream._receive_fin()
        if flags & _FLAG_RST:
            stream._receive_rst()

    def _handle_window_update(self, flags: int, stream_id: int, length: int) -> None:
        with self._lock:
            stream = self._streams.get(stream_id)
        if stream is None:
            return

        if length > 0:
            stream._update_send_window(length)
        if flags & _FLAG_FIN:
            stream._receive_fin()
        if flags & _FLAG_RST:
            stream._receive_rst()

    def _handle_ping(self, flags: int, opaque: int) -> None:
        if flags & _FLAG_SYN:
            try:
                self._send_frame(_TYPE_PING, _FLAG_ACK, 0, opaque)
            except Exception:
                pass

    # -- Keepalive ----------------------------------------------------------

    def _keepalive_loop(self) -> None:
        ping_id = 0
        while not self._shutdown_event.wait(30):
            ping_id += 1
            try:
                self._send_frame(_TYPE_PING, _FLAG_SYN, 0, ping_id)
            except Exception:
                break
