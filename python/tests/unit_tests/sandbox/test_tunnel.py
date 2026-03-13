"""Unit tests for the TCP tunnel module."""

from __future__ import annotations

import struct
import threading
from unittest.mock import MagicMock, patch

import pytest

from langsmith.sandbox._exceptions import (
    TunnelConnectionRefusedError,
    TunnelError,
    TunnelPortNotAllowedError,
    TunnelUnsupportedVersionError,
)
from langsmith.sandbox._tunnel import (
    PROTOCOL_VERSION,
    STATUS_DIAL_FAILED,
    STATUS_OK,
    STATUS_PORT_NOT_ALLOWED,
    STATUS_UNSUPPORTED_VERSION,
    AsyncTunnel,
    Tunnel,
    _read_status,
    _write_connect_header,
    _WSAdapter,
)

# ---------------------------------------------------------------------------
# _WSAdapter
# ---------------------------------------------------------------------------


class MockWS:
    """Minimal mock matching the websockets sync client interface."""

    def __init__(self, messages: list[bytes] | None = None) -> None:
        self._messages = list(messages or [])
        self._sent: list[bytes] = []
        self._closed = False

    def recv(self) -> bytes:
        if not self._messages:
            raise ConnectionError("no more messages")
        return self._messages.pop(0)

    def send(self, data: bytes) -> None:
        self._sent.append(data)

    def close(self) -> None:
        self._closed = True


class TestWSAdapter:
    def test_read_buffers_and_returns_exact(self) -> None:
        ws = MockWS([b"helloworld"])
        adapter = _WSAdapter(ws)
        assert adapter.read(5) == b"hello"
        assert adapter.read(5) == b"world"

    def test_read_spans_messages(self) -> None:
        ws = MockWS([b"he", b"ll", b"o"])
        adapter = _WSAdapter(ws)
        assert adapter.read(5) == b"hello"

    def test_write_sends_binary(self) -> None:
        ws = MockWS()
        adapter = _WSAdapter(ws)
        n = adapter.write(b"test")
        assert n == 4
        assert ws._sent == [b"test"]

    def test_write_thread_safe(self) -> None:
        ws = MockWS()
        adapter = _WSAdapter(ws)
        errors: list[Exception] = []

        def writer(val: bytes) -> None:
            try:
                for _ in range(50):
                    adapter.write(val)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(b"a",)),
            threading.Thread(target=writer, args=(b"b",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(ws._sent) == 100

    def test_close(self) -> None:
        ws = MockWS()
        adapter = _WSAdapter(ws)
        adapter.close()
        assert ws._closed

    def test_read_str_converted_to_bytes(self) -> None:
        """String messages are encoded to bytes."""
        ws = MockWS()
        ws._messages = ["hello"]  # type: ignore[list-item]
        adapter = _WSAdapter(ws)
        assert adapter.read(5) == b"hello"


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------


class MockStream:
    """Minimal stream mock for protocol helper tests."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, data: bytes) -> int:
        self._buf.extend(data)
        return len(data)

    def read(self, n: int) -> bytes:
        data = bytes(self._buf[:n])
        del self._buf[:n]
        return data


class TestProtocolHelpers:
    @pytest.mark.parametrize("port", [5432, 65535])
    def test_connect_header_encoding(self, port: int) -> None:
        stream = MockStream()
        _write_connect_header(stream, port)

        raw = bytes(stream._buf)
        assert len(raw) == 3
        version, decoded_port = struct.unpack(">BH", raw)
        assert version == PROTOCOL_VERSION
        assert decoded_port == port

    @pytest.mark.parametrize(
        "status",
        [
            STATUS_OK,
            STATUS_PORT_NOT_ALLOWED,
            STATUS_DIAL_FAILED,
            STATUS_UNSUPPORTED_VERSION,
        ],
    )
    def test_read_status(self, status: int) -> None:
        stream = MockStream()
        stream._buf = bytearray([status])
        assert _read_status(stream) == status

    def test_read_status_eof_raises(self) -> None:
        stream = MockStream()
        with pytest.raises(ConnectionError):
            _read_status(stream)


# ---------------------------------------------------------------------------
# Tunnel
# ---------------------------------------------------------------------------


class TestTunnelInit:
    def test_default_local_port_mirrors_remote(self) -> None:
        t = Tunnel("http://example.com", "key", 5432)
        assert t.remote_port == 5432
        assert t.local_port == 5432

    def test_explicit_local_port(self) -> None:
        t = Tunnel("http://example.com", "key", 5432, local_port=15432)
        assert t.local_port == 15432

    def test_build_ws_url_http(self) -> None:
        t = Tunnel("http://example.com/sandbox", "key", 5432)
        assert t._build_ws_url() == "ws://example.com/sandbox/tunnel"

    def test_build_ws_url_https(self) -> None:
        t = Tunnel("https://example.com/sandbox", "key", 5432)
        assert t._build_ws_url() == "wss://example.com/sandbox/tunnel"

    def test_build_ws_url_strips_trailing_slash(self) -> None:
        t = Tunnel("https://example.com/sandbox/", "key", 5432)
        assert t._build_ws_url() == "wss://example.com/sandbox/tunnel"


class TestTunnelContextManager:
    @patch("langsmith.sandbox._tunnel._ensure_websockets")
    def test_close_is_idempotent(self, mock_ensure: MagicMock) -> None:
        t = Tunnel("http://localhost", "key", 5432)
        t._closed = True
        t.close()  # should not raise


# ---------------------------------------------------------------------------
# AsyncTunnel
# ---------------------------------------------------------------------------


class TestAsyncTunnel:
    def test_properties_delegate(self) -> None:
        at = AsyncTunnel("http://example.com", "key", 5432, local_port=15432)
        assert at.remote_port == 5432
        assert at.local_port == 15432

    def test_close_delegates(self) -> None:
        at = AsyncTunnel("http://example.com", "key", 5432)
        at._tunnel._closed = True
        at.close()  # should not raise


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestTunnelExceptions:
    def test_tunnel_error_is_base(self) -> None:
        assert issubclass(TunnelPortNotAllowedError, TunnelError)
        assert issubclass(TunnelConnectionRefusedError, TunnelError)
        assert issubclass(TunnelUnsupportedVersionError, TunnelError)

    @pytest.mark.parametrize(
        "exc_cls,msg,port",
        [
            (TunnelPortNotAllowedError, "blocked", 5432),
            (TunnelConnectionRefusedError, "nothing listening", 6379),
        ],
    )
    def test_exception_has_port(self, exc_cls: type, msg: str, port: int) -> None:
        exc = exc_cls(msg, port=port)
        assert exc.port == port
        assert msg in str(exc)


# ---------------------------------------------------------------------------
# Port validation (tested via Sandbox.tunnel / AsyncSandbox.tunnel)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_sandbox():
    from langsmith.sandbox._sandbox import Sandbox

    sb = Sandbox(
        name="test",
        template_name="t",
        dataplane_url="http://x",
        status="ready",
    )
    sb._client = MagicMock()
    sb._client._api_key = "key"
    return sb


class TestPortValidation:
    @pytest.mark.parametrize(
        "remote,local,match",
        [
            (0, 0, "remote_port"),
            (70000, 0, "remote_port"),
            (5432, 70000, "local_port"),
        ],
    )
    def test_invalid_ports_raise(
        self, mock_sandbox: object, remote: int, local: int, match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            mock_sandbox.tunnel(remote, local_port=local)  # type: ignore[union-attr]

    @patch("langsmith.sandbox._tunnel.Tunnel._start")
    def test_valid_ports_pass_validation(
        self, mock_start: MagicMock, mock_sandbox: object
    ) -> None:
        t = mock_sandbox.tunnel(5432, local_port=15432)  # type: ignore[union-attr]
        assert isinstance(t, Tunnel)
        assert t.remote_port == 5432
        assert t.local_port == 15432
        mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# Reconnect
# ---------------------------------------------------------------------------


class TestEnsureSession:
    def test_returns_existing_live_session(self) -> None:
        t = Tunnel("http://example.com", "key", 5432)
        mock_yamux = MagicMock()
        mock_yamux.is_closed = False
        t._yamux = mock_yamux

        result = t._ensure_session()
        assert result is mock_yamux

    def test_reconnects_when_session_is_dead(self) -> None:
        t = Tunnel("http://example.com", "key", 5432)
        dead_yamux = MagicMock()
        dead_yamux.is_closed = True
        t._yamux = dead_yamux

        fresh_yamux = MagicMock()
        fresh_yamux.is_closed = False

        with patch.object(t, "_connect") as mock_connect:
            mock_connect.side_effect = lambda: setattr(t, "_yamux", fresh_yamux)
            result = t._ensure_session()

        assert result is fresh_yamux
        mock_connect.assert_called_once()

    def test_raises_after_exhausting_retries(self) -> None:
        t = Tunnel("http://example.com", "key", 5432, max_reconnects=2)
        dead_yamux = MagicMock()
        dead_yamux.is_closed = True
        t._yamux = dead_yamux
        t._BACKOFF_BASE = 0.01  # speed up test

        with patch.object(t, "_connect", side_effect=ConnectionError("fail")):
            with pytest.raises(TunnelError, match="reconnect failed"):
                t._ensure_session()

    def test_concurrent_threads_share_single_reconnect(self) -> None:
        t = Tunnel("http://example.com", "key", 5432)
        dead_yamux = MagicMock()
        dead_yamux.is_closed = True
        t._yamux = dead_yamux

        fresh_yamux = MagicMock()
        fresh_yamux.is_closed = False
        connect_count = 0

        def slow_connect() -> None:
            nonlocal connect_count
            import time

            time.sleep(0.05)
            connect_count += 1
            t._yamux = fresh_yamux

        results: list[object] = []

        def worker() -> None:
            results.append(t._ensure_session())

        with patch.object(t, "_connect", side_effect=slow_connect):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()

        assert connect_count == 1
        assert all(r is fresh_yamux for r in results)

    def test_reconnect_disabled_when_max_zero(self) -> None:
        t = Tunnel("http://example.com", "key", 5432, max_reconnects=0)
        dead_yamux = MagicMock()
        dead_yamux.is_closed = True
        t._yamux = dead_yamux

        with pytest.raises(TunnelError, match="reconnect failed"):
            t._ensure_session()
