# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..._types import Body, Query, Headers, NotGiven, not_given
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.annotation_queues.info_list_response import InfoListResponse

__all__ = ["InfoResource", "AsyncInfoResource"]


class InfoResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> InfoResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return InfoResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> InfoResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return InfoResourceWithStreamingResponse(self)

    def list(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InfoListResponse:
        """Get information about the current deployment of LangSmith."""
        return self._get(
            "/api/v1/info",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InfoListResponse,
        )


class AsyncInfoResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncInfoResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncInfoResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncInfoResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncInfoResourceWithStreamingResponse(self)

    async def list(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InfoListResponse:
        """Get information about the current deployment of LangSmith."""
        return await self._get(
            "/api/v1/info",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InfoListResponse,
        )


class InfoResourceWithRawResponse:
    def __init__(self, info: InfoResource) -> None:
        self._info = info

        self.list = to_raw_response_wrapper(
            info.list,
        )


class AsyncInfoResourceWithRawResponse:
    def __init__(self, info: AsyncInfoResource) -> None:
        self._info = info

        self.list = async_to_raw_response_wrapper(
            info.list,
        )


class InfoResourceWithStreamingResponse:
    def __init__(self, info: InfoResource) -> None:
        self._info = info

        self.list = to_streamed_response_wrapper(
            info.list,
        )


class AsyncInfoResourceWithStreamingResponse:
    def __init__(self, info: AsyncInfoResource) -> None:
        self._info = info

        self.list = async_to_streamed_response_wrapper(
            info.list,
        )
