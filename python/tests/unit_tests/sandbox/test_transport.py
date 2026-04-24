"""Tests for RetryTransport and AsyncRetryTransport."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from langsmith.sandbox._exceptions import SandboxConnectionError
from langsmith.sandbox._transport import AsyncRetryTransport, RetryTransport


class MockTransport(httpx.BaseTransport):
    """Sync mock transport that returns pre-configured responses in sequence."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = list(responses)
        self._calls: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._calls.append(request)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def call_count(self) -> int:
        return len(self._calls)


class MockAsyncTransport(httpx.AsyncBaseTransport):
    """Async mock transport that returns pre-configured responses in sequence."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = list(responses)
        self._calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self._calls.append(request)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def call_count(self) -> int:
        return len(self._calls)


def _make_request() -> httpx.Request:
    return httpx.Request("GET", "http://test-server/volumes")


# ============================================================================
# Sync RetryTransport tests
# ============================================================================


class TestRetryTransport:
    """Tests for the sync RetryTransport."""

    @pytest.mark.parametrize("status", [502, 503, 504])
    @patch("langsmith.sandbox._transport.time.sleep")
    def test_retries_on_server_error_then_succeeds(self, mock_sleep, status):
        mock = MockTransport([httpx.Response(status), httpx.Response(200)])
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2
        assert mock_sleep.call_count == 1

    @pytest.mark.parametrize(
        ("retry_after", "min_sleep"),
        [("2", 2.0), (None, 1.0), ("not-a-number", 1.0)],
        ids=["explicit", "default", "invalid"],
    )
    @patch("langsmith.sandbox._transport.time.sleep")
    def test_retries_on_429(self, mock_sleep, retry_after, min_sleep):
        headers = {"retry-after": retry_after} if retry_after else {}
        mock = MockTransport(
            [
                httpx.Response(429, headers=headers),
                httpx.Response(200),
            ]
        )
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2
        assert mock_sleep.call_args[0][0] >= min_sleep

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_retries_on_connect_error_then_succeeds(self, mock_sleep):
        mock = MockTransport(
            [
                httpx.ConnectError("Connection refused"),
                httpx.Response(200),
            ]
        )
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_exhausted_retries_on_server_error_returns_response(self, mock_sleep):
        mock = MockTransport([httpx.Response(502)] * 4)
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 502
        assert mock.call_count == 4
        assert mock_sleep.call_count == 3

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_exhausted_retries_on_connect_error_raises(self, mock_sleep):
        mock = MockTransport([httpx.ConnectError(f"fail {i}") for i in range(4)])
        transport = RetryTransport(max_retries=3, transport=mock)
        with pytest.raises(SandboxConnectionError, match="4 attempts"):
            transport.handle_request(_make_request())
        assert mock.call_count == 4

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_exhausted_retries_on_429_returns_response(self, mock_sleep):
        mock = MockTransport([httpx.Response(429, headers={"retry-after": "1"})] * 4)
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 429
        assert mock.call_count == 4

    @pytest.mark.parametrize("status", [200, 400, 401, 404, 409, 422, 500])
    def test_no_retry_on_non_retryable_status(self, status):
        mock = MockTransport([httpx.Response(status)])
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == status
        assert mock.call_count == 1

    def test_max_retries_zero_no_retry_on_server_error(self):
        mock = MockTransport([httpx.Response(502)])
        transport = RetryTransport(max_retries=0, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 502
        assert mock.call_count == 1

    def test_max_retries_zero_connect_error_raises_immediately(self):
        mock = MockTransport([httpx.ConnectError("refused")])
        transport = RetryTransport(max_retries=0, transport=mock)
        with pytest.raises(SandboxConnectionError, match="1 attempts"):
            transport.handle_request(_make_request())
        assert mock.call_count == 1

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_backoff_increases_with_attempts(self, mock_sleep):
        mock = MockTransport([httpx.Response(502)] * 3 + [httpx.Response(200)])
        transport = RetryTransport(max_retries=3, transport=mock)
        transport.handle_request(_make_request())
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_times) == 3
        for i in range(1, len(sleep_times)):
            assert sleep_times[i] >= sleep_times[i - 1]

    @patch("langsmith.sandbox._transport.time.sleep")
    def test_mixed_errors_then_success(self, mock_sleep):
        mock = MockTransport(
            [
                httpx.ConnectError("refused"),
                httpx.Response(502),
                httpx.Response(200),
            ]
        )
        transport = RetryTransport(max_retries=3, transport=mock)
        response = transport.handle_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 3

    def test_connect_error_preserves_cause(self):
        original = httpx.ConnectError("the cause")
        mock = MockTransport([original])
        transport = RetryTransport(max_retries=0, transport=mock)
        with pytest.raises(SandboxConnectionError) as exc_info:
            transport.handle_request(_make_request())
        assert exc_info.value.__cause__ is original


# ============================================================================
# Async AsyncRetryTransport tests
# ============================================================================


class TestAsyncRetryTransport:
    """Tests for the async AsyncRetryTransport."""

    @pytest.fixture
    def _patch_sleep(self):
        with patch("langsmith.sandbox._transport.asyncio.sleep") as mock:
            yield mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [502, 503, 504])
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_retries_on_server_error_then_succeeds(self, status):
        mock = MockAsyncTransport([httpx.Response(status), httpx.Response(200)])
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_retries_on_429_with_retry_after(self, _patch_sleep):
        mock = MockAsyncTransport(
            [
                httpx.Response(429, headers={"retry-after": "2"}),
                httpx.Response(200),
            ]
        )
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2
        assert _patch_sleep.call_args[0][0] >= 2.0

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_retries_on_connect_error_then_succeeds(self):
        mock = MockAsyncTransport(
            [
                httpx.ConnectError("Connection refused"),
                httpx.Response(200),
            ]
        )
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_exhausted_retries_on_server_error_returns_response(self):
        mock = MockAsyncTransport([httpx.Response(502)] * 4)
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 502
        assert mock.call_count == 4

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_exhausted_retries_on_connect_error_raises(self):
        mock = MockAsyncTransport([httpx.ConnectError(f"fail {i}") for i in range(4)])
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        with pytest.raises(SandboxConnectionError, match="4 attempts"):
            await transport.handle_async_request(_make_request())
        assert mock.call_count == 4

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_exhausted_retries_on_429_returns_response(self):
        mock = MockAsyncTransport(
            [httpx.Response(429, headers={"retry-after": "1"})] * 4
        )
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 429
        assert mock.call_count == 4

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [200, 400, 404, 500])
    async def test_no_retry_on_non_retryable_status(self, status):
        mock = MockAsyncTransport([httpx.Response(status)])
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == status
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_zero_no_retry_on_server_error(self):
        mock = MockAsyncTransport([httpx.Response(502)])
        transport = AsyncRetryTransport(max_retries=0, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 502
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_zero_connect_error_raises_immediately(self):
        mock = MockAsyncTransport([httpx.ConnectError("refused")])
        transport = AsyncRetryTransport(max_retries=0, transport=mock)
        with pytest.raises(SandboxConnectionError, match="1 attempts"):
            await transport.handle_async_request(_make_request())
        assert mock.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_patch_sleep")
    async def test_mixed_errors_then_success(self):
        mock = MockAsyncTransport(
            [
                httpx.ConnectError("refused"),
                httpx.Response(502),
                httpx.Response(200),
            ]
        )
        transport = AsyncRetryTransport(max_retries=3, transport=mock)
        response = await transport.handle_async_request(_make_request())
        assert response.status_code == 200
        assert mock.call_count == 3

    @pytest.mark.asyncio
    async def test_connect_error_preserves_cause(self):
        original = httpx.ConnectError("the cause")
        mock = MockAsyncTransport([original])
        transport = AsyncRetryTransport(max_retries=0, transport=mock)
        with pytest.raises(SandboxConnectionError) as exc_info:
            await transport.handle_async_request(_make_request())
        assert exc_info.value.__cause__ is original
