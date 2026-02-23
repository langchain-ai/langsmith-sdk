"""Tests for async WebSocket transport helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from langsmith.sandbox._ws_execute import _AsyncWSStreamControl

# =============================================================================
# Tests: _AsyncWSStreamControl
# =============================================================================


class TestAsyncWSStreamControl:
    def test_initial_state(self):
        ctrl = _AsyncWSStreamControl()
        assert ctrl.killed is False

    def test_bind_unbind(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        ctrl._bind(ws)
        assert ctrl._ws is ws
        ctrl._unbind()
        assert ctrl._ws is None
        assert ctrl._closed is True

    @pytest.mark.asyncio
    async def test_send_kill(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        await ctrl.send_kill()
        assert ctrl.killed is True
        assert json.loads(sent[0]) == {"type": "kill"}

    @pytest.mark.asyncio
    async def test_send_kill_when_closed(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        ctrl._unbind()
        await ctrl.send_kill()
        assert ctrl.killed is True
        assert sent == []

    @pytest.mark.asyncio
    async def test_send_input(self):
        ctrl = _AsyncWSStreamControl()
        ws = MagicMock()
        sent: list[str] = []

        async def mock_send(data: str) -> None:
            sent.append(data)

        ws.send = mock_send
        ctrl._bind(ws)
        await ctrl.send_input("hello\n")
        assert json.loads(sent[0]) == {
            "type": "input",
            "data": "hello\n",
        }
