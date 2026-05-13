# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime

import httpx

from .traces import (
    TracesResource,
    AsyncTracesResource,
    TracesResourceWithRawResponse,
    AsyncTracesResourceWithRawResponse,
    TracesResourceWithStreamingResponse,
    AsyncTracesResourceWithStreamingResponse,
)
from ...types import thread_query_params
from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import SyncItemsCursorPostPagination, AsyncItemsCursorPostPagination
from ..._base_client import AsyncPaginator, make_request_options
from ...types.thread_list_item import ThreadListItem

__all__ = ["ThreadsResource", "AsyncThreadsResource"]


class ThreadsResource(SyncAPIResource):
    @cached_property
    def traces(self) -> TracesResource:
        return TracesResource(self._client)

    @cached_property
    def with_raw_response(self) -> ThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ThreadsResourceWithStreamingResponse(self)

    def query(
        self,
        *,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorPostPagination[ThreadListItem]:
        """
        **Alpha:** The request and response contract may change; Query threads within a
        project (session), with cursor-based pagination. Returns threads matching the
        given time range and optional filter.

        Args:
          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Omit on
              the first request; pass the returned cursor to fetch the next page.

          filter: `filter` narrows which threads are returned, using a LangSmith filter expression
              evaluated against each thread's root run. For example: has(tags, "production")
              or eq(status, "error"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          max_start_time: `max_start_time` is the inclusive upper bound on thread activity (RFC3339
              date-time).

          min_start_time: `min_start_time` is the inclusive lower bound on thread activity (RFC3339
              date-time).

          page_size: `page_size` is the maximum number of threads to return in this response.
              Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
              response may contain fewer threads than `page_size` even when `has_more` is
              true.

          project_id: `project_id` is the tracing project UUID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/threads/query",
            page=SyncItemsCursorPostPagination[ThreadListItem],
            body=maybe_transform(
                {
                    "cursor": cursor,
                    "filter": filter,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_id": project_id,
                },
                thread_query_params.ThreadQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ThreadListItem,
            method="post",
        )


class AsyncThreadsResource(AsyncAPIResource):
    @cached_property
    def traces(self) -> AsyncTracesResource:
        return AsyncTracesResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncThreadsResourceWithStreamingResponse(self)

    def query(
        self,
        *,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[ThreadListItem, AsyncItemsCursorPostPagination[ThreadListItem]]:
        """
        **Alpha:** The request and response contract may change; Query threads within a
        project (session), with cursor-based pagination. Returns threads matching the
        given time range and optional filter.

        Args:
          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Omit on
              the first request; pass the returned cursor to fetch the next page.

          filter: `filter` narrows which threads are returned, using a LangSmith filter expression
              evaluated against each thread's root run. For example: has(tags, "production")
              or eq(status, "error"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          max_start_time: `max_start_time` is the inclusive upper bound on thread activity (RFC3339
              date-time).

          min_start_time: `min_start_time` is the inclusive lower bound on thread activity (RFC3339
              date-time).

          page_size: `page_size` is the maximum number of threads to return in this response.
              Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
              response may contain fewer threads than `page_size` even when `has_more` is
              true.

          project_id: `project_id` is the tracing project UUID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/threads/query",
            page=AsyncItemsCursorPostPagination[ThreadListItem],
            body=maybe_transform(
                {
                    "cursor": cursor,
                    "filter": filter,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_id": project_id,
                },
                thread_query_params.ThreadQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ThreadListItem,
            method="post",
        )


class ThreadsResourceWithRawResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.query = to_raw_response_wrapper(
            threads.query,
        )

    @cached_property
    def traces(self) -> TracesResourceWithRawResponse:
        return TracesResourceWithRawResponse(self._threads.traces)


class AsyncThreadsResourceWithRawResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.query = async_to_raw_response_wrapper(
            threads.query,
        )

    @cached_property
    def traces(self) -> AsyncTracesResourceWithRawResponse:
        return AsyncTracesResourceWithRawResponse(self._threads.traces)


class ThreadsResourceWithStreamingResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.query = to_streamed_response_wrapper(
            threads.query,
        )

    @cached_property
    def traces(self) -> TracesResourceWithStreamingResponse:
        return TracesResourceWithStreamingResponse(self._threads.traces)


class AsyncThreadsResourceWithStreamingResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.query = async_to_streamed_response_wrapper(
            threads.query,
        )

    @cached_property
    def traces(self) -> AsyncTracesResourceWithStreamingResponse:
        return AsyncTracesResourceWithStreamingResponse(self._threads.traces)
