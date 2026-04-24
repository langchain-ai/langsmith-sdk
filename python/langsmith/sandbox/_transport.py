"""Custom httpx transports with retry logic for the sandbox client.

Provides RetryTransport (sync) and AsyncRetryTransport (async) that wrap
the default httpx transports with automatic retry on transient errors.
This mirrors the main LangSmith client's _LangSmithHttpAdapter + urllib3.Retry
architecture at the transport level, making retries transparent to all call sites.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx

from langsmith.sandbox._exceptions import SandboxConnectionError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

_MAX_BACKOFF = 10.0


def _compute_backoff(attempt: int) -> float:
    """Compute exponential backoff with jitter, capped at _MAX_BACKOFF."""
    return min(2**attempt + random.random(), _MAX_BACKOFF)


class RetryTransport(httpx.BaseTransport):
    """Sync httpx transport that retries on transient errors.

    Retries on:
    - 502/503/504 with exponential backoff
    - 429 with Retry-After header support
    - Connection errors with exponential backoff

    After exhausting retries, the last response is returned (for status errors)
    or SandboxConnectionError is raised (for connection errors).
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._transport = transport or httpx.HTTPTransport()
        self._max_retries = max_retries

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries + 1):
            is_last_attempt = attempt == self._max_retries

            try:
                response = self._transport.handle_request(request)
                last_response = response

                if not is_last_attempt:
                    if response.status_code in RETRYABLE_STATUS_CODES:
                        response.close()
                        sleep_time = _compute_backoff(attempt)
                        logger.debug(
                            "Retrying %s %s (status %d, attempt %d/%d, sleeping %.1fs)",
                            request.method,
                            request.url,
                            response.status_code,
                            attempt + 1,
                            self._max_retries,
                            sleep_time,
                        )
                        time.sleep(sleep_time)
                        continue

                    if response.status_code == 429:
                        retry_after = _parse_retry_after(response)
                        sleep_time = retry_after * 2**attempt + random.random()
                        response.close()
                        logger.debug(
                            "Rate limited on %s %s, retrying after %.1fs "
                            "(attempt %d/%d)",
                            request.method,
                            request.url,
                            sleep_time,
                            attempt + 1,
                            self._max_retries,
                        )
                        time.sleep(sleep_time)
                        continue

                return response

            except httpx.ConnectError as exc:
                if not is_last_attempt:
                    sleep_time = _compute_backoff(attempt)
                    logger.debug(
                        "Connection error on %s %s, retrying "
                        "(attempt %d/%d, sleeping %.1fs): %s",
                        request.method,
                        request.url,
                        attempt + 1,
                        self._max_retries,
                        sleep_time,
                        exc,
                    )
                    time.sleep(sleep_time)
                    continue
                raise SandboxConnectionError(
                    f"Failed to connect to server after "
                    f"{self._max_retries + 1} attempts: {exc}"
                ) from exc

        assert last_response is not None
        return last_response

    def close(self) -> None:
        self._transport.close()


class AsyncRetryTransport(httpx.AsyncBaseTransport):
    """Async httpx transport that retries on transient errors.

    Async equivalent of RetryTransport. See RetryTransport for details.
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport or httpx.AsyncHTTPTransport()
        self._max_retries = max_retries

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries + 1):
            is_last_attempt = attempt == self._max_retries

            try:
                response = await self._transport.handle_async_request(request)
                last_response = response

                if not is_last_attempt:
                    if response.status_code in RETRYABLE_STATUS_CODES:
                        await response.aclose()
                        sleep_time = _compute_backoff(attempt)
                        logger.debug(
                            "Retrying %s %s (status %d, attempt %d/%d, sleeping %.1fs)",
                            request.method,
                            request.url,
                            response.status_code,
                            attempt + 1,
                            self._max_retries,
                            sleep_time,
                        )
                        await asyncio.sleep(sleep_time)
                        continue

                    if response.status_code == 429:
                        retry_after = _parse_retry_after(response)
                        sleep_time = retry_after * 2**attempt + random.random()
                        await response.aclose()
                        logger.debug(
                            "Rate limited on %s %s, retrying after %.1fs "
                            "(attempt %d/%d)",
                            request.method,
                            request.url,
                            sleep_time,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(sleep_time)
                        continue

                return response

            except httpx.ConnectError as exc:
                if not is_last_attempt:
                    sleep_time = _compute_backoff(attempt)
                    logger.debug(
                        "Connection error on %s %s, retrying "
                        "(attempt %d/%d, sleeping %.1fs): %s",
                        request.method,
                        request.url,
                        attempt + 1,
                        self._max_retries,
                        sleep_time,
                        exc,
                    )
                    await asyncio.sleep(sleep_time)
                    continue
                raise SandboxConnectionError(
                    f"Failed to connect to server after "
                    f"{self._max_retries + 1} attempts: {exc}"
                ) from exc

        assert last_response is not None
        return last_response

    async def aclose(self) -> None:
        await self._transport.aclose()


def _parse_retry_after(response: httpx.Response) -> float:
    """Parse Retry-After header value, defaulting to 1.0 second."""
    raw = response.headers.get("retry-after", "1")
    try:
        return max(float(raw), 0.0)
    except (ValueError, TypeError):
        return 1.0
