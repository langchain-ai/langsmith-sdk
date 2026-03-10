"""Tests for interactive PTY sessions (async)."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langsmith.sandbox._async_session import AsyncSession
from langsmith.sandbox._exceptions import (
    SandboxConnectionError,
    SandboxOperationError,
    SandboxServerReloadError,
)
from langsmith.sandbox._ws_session import _AsyncSessionWSControl


# =============================================================================
# Helpers
# =============================================================================


def _make_sandbox_mock() -> Any:
    """Create a mock AsyncSandbox with dataplane_url and client."""
    sandbox = MagicMock()
    sandbox._require_dataplane_url.return_value = "https://router.example.com/sb-123"
    sandbox._client._api_key = "test-key"
    sandbox._client._http = AsyncMock()
    return sandbox


async def _async_output_iter(chunks: list[str]) -> AsyncIterator[str]:
    for chunk in chunks:
        yield chunk


# =============================================================================
# Tests: _AsyncSessionWSControl
# =============================================================================


class TestAsyncSessionWSControl:
    def test_initial_state(self):
        ctrl = _AsyncSessionWSControl()
        assert ctrl.connected is False

    def test_bind_unbind(self):
        ctrl = _AsyncSessionWSControl()
        ws = MagicMock()
        ctrl._bind(ws)
        assert ctrl.connected is True
        ctrl._unbind()
        assert ctrl.connected is False

    @pytest.mark.asyncio
    async def test_send_input_base64_encodes(self):
        ctrl = _AsyncSessionWSControl()
        ws = AsyncMock()
        ctrl._bind(ws)
        await ctrl.send_input("hello\n")
        expected_b64 = base64.b64encode(b"hello\n").decode("ascii")
        ws.send.assert_called_once_with(
            json.dumps({"type": "input", "data": expected_b64})
        )

    @pytest.mark.asyncio
    async def test_send_resize(self):
        ctrl = _AsyncSessionWSControl()
        ws = AsyncMock()
        ctrl._bind(ws)
        await ctrl.send_resize(120, 40)
        ws.send.assert_called_once_with(
            json.dumps({"type": "resize", "cols": 120, "rows": 40})
        )

    @pytest.mark.asyncio
    async def test_send_input_when_closed(self):
        ctrl = _AsyncSessionWSControl()
        ws = AsyncMock()
        ctrl._bind(ws)
        ctrl._unbind()
        await ctrl.send_input("data")
        ws.send.assert_not_called()



# =============================================================================
# Tests: AsyncSession lifecycle
# =============================================================================


class TestAsyncSession:
    def test_properties(self):
        sandbox = _make_sandbox_mock()
        session = AsyncSession("sess-1", sandbox, shell="/bin/bash", workdir="/home")
        assert session.session_id == "sess-1"
        assert session.connected is False

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_connect_disconnect(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _AsyncSessionWSControl()
        ctrl._bind(MagicMock())
        mock_connect.return_value = (_async_output_iter([]), ctrl)

        session = AsyncSession("sess-1", sandbox)
        await session.connect()
        assert session.connected is True

        await session.disconnect()
        assert session.connected is False

    @pytest.mark.asyncio
    async def test_send_input_not_connected_raises(self):
        sandbox = _make_sandbox_mock()
        session = AsyncSession("sess-1", sandbox)
        with pytest.raises(SandboxOperationError, match="not connected"):
            await session.send_input("hello")

    @pytest.mark.asyncio
    async def test_resize_not_connected_raises(self):
        sandbox = _make_sandbox_mock()
        session = AsyncSession("sess-1", sandbox)
        with pytest.raises(SandboxOperationError, match="not connected"):
            await session.resize(80, 24)

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_send_input_connected(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _AsyncSessionWSControl()
        ws = AsyncMock()
        ctrl._bind(ws)
        mock_connect.return_value = (_async_output_iter([]), ctrl)

        session = AsyncSession("sess-1", sandbox)
        await session.connect()
        await session.send_input("ls\n")

        expected_b64 = base64.b64encode(b"ls\n").decode("ascii")
        ws.send.assert_called_once_with(
            json.dumps({"type": "input", "data": expected_b64})
        )

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_resize_connected(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _AsyncSessionWSControl()
        ws = AsyncMock()
        ctrl._bind(ws)
        mock_connect.return_value = (_async_output_iter([]), ctrl)

        session = AsyncSession("sess-1", sandbox)
        await session.connect()
        await session.resize(120, 40)

        ws.send.assert_called_once_with(
            json.dumps({"type": "resize", "cols": 120, "rows": 40})
        )

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_iteration_yields_output(self, mock_connect):
        sandbox = _make_sandbox_mock()
        ctrl = _AsyncSessionWSControl()
        ctrl._bind(MagicMock())
        mock_connect.return_value = (_async_output_iter(["hello", " world"]), ctrl)

        session = AsyncSession("sess-1", sandbox)
        await session.connect()
        output = [chunk async for chunk in session]
        assert output == ["hello", " world"]

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_auto_reconnect_on_connection_error(self, mock_connect):
        sandbox = _make_sandbox_mock()
        call_count = [0]

        async def make_connect(*args, **kwargs):
            call_count[0] += 1
            ctrl = _AsyncSessionWSControl()
            ctrl._bind(MagicMock())
            if call_count[0] == 1:

                async def failing():
                    yield "part1"
                    raise SandboxConnectionError("lost")

                return failing(), ctrl
            else:

                async def succeeding():
                    yield "part2"

                return succeeding(), ctrl

        mock_connect.side_effect = make_connect

        session = AsyncSession("sess-1", sandbox)
        await session.connect()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            output = [chunk async for chunk in session]

        assert output == ["part1", "part2"]
        assert call_count[0] == 2
        mock_sleep.assert_called_once_with(0.5)

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_auto_reconnect_server_reload_no_backoff(self, mock_connect):
        sandbox = _make_sandbox_mock()
        call_count = [0]

        async def make_connect(*args, **kwargs):
            call_count[0] += 1
            ctrl = _AsyncSessionWSControl()
            ctrl._bind(MagicMock())
            if call_count[0] == 1:

                async def failing():
                    yield "data"
                    raise SandboxServerReloadError("reloading")

                return failing(), ctrl
            else:
                return _async_output_iter(["more"]), ctrl

        mock_connect.side_effect = make_connect

        session = AsyncSession("sess-1", sandbox)
        await session.connect()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            output = [chunk async for chunk in session]
            mock_sleep.assert_not_called()

        assert output == ["data", "more"]

    @pytest.mark.asyncio
    @patch("langsmith.sandbox._async_session.connect_session_ws_async")
    async def test_max_reconnects_exceeded(self, mock_connect):
        sandbox = _make_sandbox_mock()

        async def make_connect(*args, **kwargs):
            ctrl = _AsyncSessionWSControl()
            ctrl._bind(MagicMock())

            async def failing():
                raise SandboxConnectionError("lost")
                yield  # make it an async generator  # noqa: E501

            return failing(), ctrl

        mock_connect.side_effect = make_connect

        session = AsyncSession("sess-1", sandbox)
        await session.connect()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SandboxConnectionError, match="giving up"):
                _ = [chunk async for chunk in session]

    @pytest.mark.asyncio
    async def test_close_calls_http_delete(self):
        sandbox = _make_sandbox_mock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        sandbox._client._http.delete.return_value = mock_response

        session = AsyncSession("sess-1", sandbox)
        await session.close()

        sandbox._client._http.delete.assert_called_once_with(
            "https://router.example.com/sb-123/sessions/sess-1",
            timeout=30,
        )

    @pytest.mark.asyncio
    async def test_context_manager_calls_close(self):
        sandbox = _make_sandbox_mock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        sandbox._client._http.delete.return_value = mock_response

        session = AsyncSession("sess-1", sandbox)
        async with session:
            pass

        sandbox._client._http.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_suppresses_close_errors(self):
        sandbox = _make_sandbox_mock()
        sandbox._client._http.delete.side_effect = Exception("network error")

        session = AsyncSession("sess-1", sandbox)
        async with session:
            pass  # Should not raise
