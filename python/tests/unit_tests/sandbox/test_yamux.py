"""Unit tests for the yamux multiplexing implementation."""

from __future__ import annotations

import struct
import threading
import time

import pytest

from langsmith.sandbox._yamux import (
    _FLAG_ACK,
    _FLAG_FIN,
    _FLAG_RST,
    _FLAG_SYN,
    _HEADER_FMT,
    _HEADER_SIZE,
    _INITIAL_WINDOW_SIZE,
    _TYPE_DATA,
    _TYPE_GO_AWAY,
    _TYPE_PING,
    _TYPE_WINDOW_UPDATE,
    _VERSION,
    YamuxSession,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class MockConn:
    """In-memory byte-stream for testing yamux without real I/O.

    Writes are buffered and can be inspected.  Data to be read by the
    session can be injected via :meth:`feed`.
    """

    def __init__(self) -> None:
        self._read_buf = bytearray()
        self._write_buf = bytearray()
        self._cond = threading.Condition()
        self._closed = False

    def feed(self, data: bytes) -> None:
        """Inject bytes that ``read()`` will return."""
        with self._cond:
            self._read_buf.extend(data)
            self._cond.notify_all()

    def read(self, n: int) -> bytes:
        with self._cond:
            while len(self._read_buf) < n and not self._closed:
                if not self._cond.wait(timeout=5):
                    raise TimeoutError("MockConn.read timed out")
            if len(self._read_buf) < n:
                raise ConnectionError("MockConn closed")
            data = bytes(self._read_buf[:n])
            del self._read_buf[:n]
            return data

    def write(self, data: bytes) -> int:
        with self._cond:
            if self._closed:
                raise ConnectionError("MockConn closed")
            self._write_buf.extend(data)
        return len(data)

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    # -- Inspection helpers --------------------------------------------------

    def drain_written(self) -> bytes:
        """Return and clear everything written so far."""
        with self._cond:
            data = bytes(self._write_buf)
            self._write_buf.clear()
            return data

    def read_frame(self) -> tuple[int, int, int, int, int, bytes]:
        """Parse one yamux frame from the write buffer.

        Returns (version, msg_type, flags, stream_id, length, payload).
        Payload is only present for DATA frames.
        """
        with self._cond:
            while len(self._write_buf) < _HEADER_SIZE:
                if not self._cond.wait(timeout=2):
                    raise TimeoutError("read_frame: no frame available")

            hdr_bytes = bytes(self._write_buf[:_HEADER_SIZE])
            del self._write_buf[:_HEADER_SIZE]

        ver, mtype, flags, sid, length = struct.unpack(_HEADER_FMT, hdr_bytes)

        payload = b""
        if mtype == _TYPE_DATA and length > 0:
            with self._cond:
                while len(self._write_buf) < length:
                    if not self._cond.wait(timeout=2):
                        raise TimeoutError("read_frame: incomplete payload")
                payload = bytes(self._write_buf[:length])
                del self._write_buf[:length]

        return ver, mtype, flags, sid, length, payload


def _make_frame(
    msg_type: int,
    flags: int,
    stream_id: int,
    length: int,
    payload: bytes = b"",
) -> bytes:
    """Build a raw yamux frame."""
    hdr = struct.pack(_HEADER_FMT, _VERSION, msg_type, flags, stream_id, length)
    return hdr + payload


# ---------------------------------------------------------------------------
# YamuxSession.open_stream
# ---------------------------------------------------------------------------


class TestOpenStream:
    def test_sends_syn(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            assert stream.stream_id == 1

            ver, mtype, flags, sid, length, _ = conn.read_frame()
            assert mtype == _TYPE_WINDOW_UPDATE
            assert flags == _FLAG_SYN
            assert sid == 1
            assert length == 0
        finally:
            session.close()

    def test_stream_ids_are_odd_and_increasing(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            s1 = session.open_stream()
            s2 = session.open_stream()
            s3 = session.open_stream()
            assert s1.stream_id == 1
            assert s2.stream_id == 3
            assert s3.stream_id == 5
        finally:
            session.close()

    def test_open_after_close_raises(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        session.close()
        with pytest.raises(RuntimeError, match="closed"):
            session.open_stream()


# ---------------------------------------------------------------------------
# Stream write
# ---------------------------------------------------------------------------


class TestStreamWrite:
    def test_write_sends_data_frame(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()  # clear SYN

            stream.write(b"hello")

            ver, mtype, flags, sid, length, payload = conn.read_frame()
            assert mtype == _TYPE_DATA
            assert flags == 0
            assert sid == stream.stream_id
            assert length == 5
            assert payload == b"hello"
        finally:
            session.close()

    def test_write_respects_send_window(self) -> None:
        """Write blocks when the send window is exhausted."""
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()

            stream._send_window = 3

            result = stream.write(b"abc")
            assert result == 3

            _, _, _, _, length, payload = conn.read_frame()
            assert length == 3
            assert payload == b"abc"
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Stream read (data dispatched by read loop)
# ---------------------------------------------------------------------------


class TestStreamRead:
    def test_read_receives_data(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()

            frame = _make_frame(_TYPE_DATA, 0, stream.stream_id, 5, b"hello")
            conn.feed(frame)

            data = stream.read(5)
            assert data == b"hello"
        finally:
            session.close()

    def test_read_partial(self) -> None:
        """read(n) returns up to n bytes even if more are buffered."""
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()

            conn.feed(_make_frame(_TYPE_DATA, 0, stream.stream_id, 10, b"helloworld"))
            time.sleep(0.05)

            chunk1 = stream.read(5)
            assert chunk1 == b"hello"
            chunk2 = stream.read(5)
            assert chunk2 == b"world"
        finally:
            session.close()

    def test_read_blocks_until_data(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            received: list[bytes] = []

            def reader() -> None:
                received.append(stream.read(3))

            t = threading.Thread(target=reader)
            t.start()

            time.sleep(0.05)
            assert not received

            conn.feed(_make_frame(_TYPE_DATA, 0, stream.stream_id, 3, b"abc"))
            t.join(timeout=2)

            assert received == [b"abc"]
        finally:
            session.close()


# ---------------------------------------------------------------------------
# FIN / RST handling
# ---------------------------------------------------------------------------


class TestFinRst:
    def test_fin_causes_eof(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.feed(_make_frame(_TYPE_DATA, _FLAG_FIN, stream.stream_id, 0))
            time.sleep(0.05)

            data = stream.read(1024)
            assert data == b""
        finally:
            session.close()

    def test_fin_after_data_drains_buffer_first(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()

            conn.feed(_make_frame(_TYPE_DATA, _FLAG_FIN, stream.stream_id, 3, b"end"))
            time.sleep(0.05)

            assert stream.read(3) == b"end"
            assert stream.read(1) == b""
        finally:
            session.close()

    def test_rst_raises_on_read(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.feed(_make_frame(_TYPE_DATA, _FLAG_RST, stream.stream_id, 0))
            time.sleep(0.05)

            with pytest.raises(ConnectionResetError):
                stream.read(1)
        finally:
            session.close()

    def test_rst_drains_buffer_before_error(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.feed(_make_frame(_TYPE_DATA, 0, stream.stream_id, 2, b"ok"))
            time.sleep(0.05)
            conn.feed(_make_frame(_TYPE_DATA, _FLAG_RST, stream.stream_id, 0))
            time.sleep(0.05)

            assert stream.read(2) == b"ok"
            with pytest.raises(ConnectionResetError):
                stream.read(1)
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Ping / pong
# ---------------------------------------------------------------------------


class TestPing:
    def test_responds_to_ping_with_ack(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            conn.drain_written()

            conn.feed(_make_frame(_TYPE_PING, _FLAG_SYN, 0, 42))
            time.sleep(0.1)

            ver, mtype, flags, sid, opaque, _ = conn.read_frame()
            assert mtype == _TYPE_PING
            assert flags == _FLAG_ACK
            assert opaque == 42
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Window updates
# ---------------------------------------------------------------------------


class TestWindowUpdate:
    def test_window_update_increases_send_window(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            initial = stream._send_window

            conn.feed(_make_frame(_TYPE_WINDOW_UPDATE, 0, stream.stream_id, 1024))
            time.sleep(0.05)

            assert stream._send_window == initial + 1024
        finally:
            session.close()

    def test_batched_window_update_on_read(self) -> None:
        """A window update is sent after consuming >= half the window."""
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()

            half = _INITIAL_WINDOW_SIZE // 2
            payload = b"\x00" * half
            conn.feed(_make_frame(_TYPE_DATA, 0, stream.stream_id, half, payload))
            time.sleep(0.05)

            stream.read(half)
            time.sleep(0.05)

            ver, mtype, flags, sid, delta, _ = conn.read_frame()
            assert mtype == _TYPE_WINDOW_UPDATE
            assert sid == stream.stream_id
            assert delta == half
        finally:
            session.close()

    def test_no_update_for_small_reads(self) -> None:
        """Small reads don't trigger window updates."""
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()

            conn.feed(_make_frame(_TYPE_DATA, 0, stream.stream_id, 10, b"0123456789"))
            time.sleep(0.05)

            stream.read(10)
            time.sleep(0.05)

            remaining = conn.drain_written()
            assert len(remaining) == 0
        finally:
            session.close()


# ---------------------------------------------------------------------------
# GoAway
# ---------------------------------------------------------------------------


class TestGoAway:
    def test_go_away_closes_session(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            conn.feed(_make_frame(_TYPE_GO_AWAY, 0, 0, 0))
            time.sleep(0.1)
            assert session.is_closed
        finally:
            session.close()

    def test_go_away_resets_open_streams(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.feed(_make_frame(_TYPE_GO_AWAY, 0, 0, 0))
            time.sleep(0.1)

            with pytest.raises(ConnectionResetError):
                stream.read(1)
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Session close
# ---------------------------------------------------------------------------


class TestSessionClose:
    def test_close_sends_go_away(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        conn.drain_written()

        session.close()

        ver, mtype, flags, sid, length, _ = conn.read_frame()
        assert mtype == _TYPE_GO_AWAY

    def test_close_is_idempotent(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        session.close()
        session.close()  # should not raise


# ---------------------------------------------------------------------------
# Multiple concurrent streams
# ---------------------------------------------------------------------------


class TestConcurrentStreams:
    def test_interleaved_data(self) -> None:
        """Data for different streams is dispatched correctly."""
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            s1 = session.open_stream()
            s2 = session.open_stream()

            conn.feed(_make_frame(_TYPE_DATA, 0, s1.stream_id, 1, b"A"))
            conn.feed(_make_frame(_TYPE_DATA, 0, s2.stream_id, 1, b"B"))
            conn.feed(_make_frame(_TYPE_DATA, 0, s1.stream_id, 1, b"C"))
            time.sleep(0.1)

            assert s1.read(1) == b"A"
            assert s2.read(1) == b"B"
            assert s1.read(1) == b"C"
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Stream close
# ---------------------------------------------------------------------------


class TestStreamClose:
    def test_close_sends_fin(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            conn.drain_written()

            stream.close()

            ver, mtype, flags, sid, length, _ = conn.read_frame()
            assert mtype == _TYPE_DATA
            assert flags == _FLAG_FIN
            assert sid == stream.stream_id
        finally:
            session.close()

    def test_write_after_close_raises(self) -> None:
        conn = MockConn()
        session = YamuxSession(conn)
        try:
            stream = session.open_stream()
            stream.close()

            with pytest.raises(BrokenPipeError):
                stream.write(b"x")
        finally:
            session.close()
