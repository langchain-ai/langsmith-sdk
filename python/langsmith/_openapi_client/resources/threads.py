# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..types import thread_query_params, thread_stats_params, thread_list_traces_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import path_template, maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..pagination import (
    SyncItemsCursorGetPagination,
    AsyncItemsCursorGetPagination,
    SyncItemsCursorPostPagination,
    AsyncItemsCursorPostPagination,
)
from .._base_client import AsyncPaginator, make_request_options
from ..types.thread import Thread
from ..types.thread_stats import ThreadStats
from ..types.thread_trace import ThreadTrace

__all__ = ["ThreadsResource", "AsyncThreadsResource"]


class ThreadsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return ThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return ThreadsResourceWithStreamingResponse(self)

    def list_traces(
        self,
        thread_id: str,
        *,
        project_id: str,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        page_size: int | Omit = omit,
        selects: List[
            Literal[
                "THREAD_ID",
                "TRACE_ID",
                "OP",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_TOKENS",
                "START_TIME",
                "END_TIME",
                "LATENCY",
                "FIRST_TOKEN_TIME",
                "INPUTS_PREVIEW",
                "OUTPUTS_PREVIEW",
                "PROMPT_COST",
                "COMPLETION_COST",
                "TOTAL_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "NAME",
                "ERROR_PREVIEW",
            ]
        ]
        | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorGetPagination[ThreadTrace]:
        """
        **Alpha:** The request and response contract may change; Retrieve all traces
        belonging to a specific thread within a project.

        Args:
          project_id: `project_id` is the tracing project UUID (required).

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Omit on
              the first request; pass the returned cursor to fetch the next page.

          filter: `filter` narrows which traces are returned for this thread, using a LangSmith
              filter expression evaluated against each root trace run. For example: eq(status,
              "success") or has(tags, "production"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          page_size: `page_size` is the maximum number of traces to return in this response. Defaults
              to 20 when omitted; must be between 1 and 100 inclusive when set.

          selects: `selects` lists which properties to include on each returned trace (repeatable
              query parameter). Accepts any value of the `ThreadTraceSelectField` enum.
              Properties not listed are omitted from each trace object; `trace_id` is always
              returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return self._get_api_list(
            path_template("/v2/threads/{thread_id}/traces", thread_id=thread_id),
            page=SyncItemsCursorGetPagination[ThreadTrace],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "project_id": project_id,
                        "cursor": cursor,
                        "filter": filter,
                        "page_size": page_size,
                        "selects": selects,
                    },
                    thread_list_traces_params.ThreadListTracesParams,
                ),
            ),
            model=ThreadTrace,
        )

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
    ) -> SyncItemsCursorPostPagination[Thread]:
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

          max_start_time: `max_start_time` is the exclusive upper bound on thread activity (RFC3339
              date-time). Defaults to now (UTC) when omitted.

          min_start_time: `min_start_time` is the inclusive lower bound on thread activity (RFC3339
              date-time). Defaults to 1 day before now (UTC) when omitted.

          page_size: `page_size` is the maximum number of threads to return in this response.
              Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
              response may contain fewer threads than `page_size` even when `next_cursor` is
              non-null.

          project_id: `project_id` is the tracing project UUID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/threads/query",
            page=SyncItemsCursorPostPagination[Thread],
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
            model=Thread,
            method="post",
        )

    def stats(
        self,
        thread_id: str,
        *,
        selects: List[
            Literal[
                "TURNS",
                "FIRST_START_TIME",
                "LAST_START_TIME",
                "LAST_END_TIME",
                "LATENCY_P50",
                "LATENCY_P99",
                "PROMPT_TOKENS",
                "PROMPT_COST",
                "COMPLETION_TOKENS",
                "COMPLETION_COST",
                "TOTAL_TOKENS",
                "TOTAL_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "FEEDBACK_STATS",
            ]
        ],
        session_id: str,
        filter: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ThreadStats:
        """
        **Alpha:** The request and response contract may change; Compute aggregate stats
        for a single thread (turn count, latency percentiles, token/cost sums, and
        detail breakdowns) within a project.

        Args:
          selects: `selects` lists which aggregate stats to compute and return (repeatable query
              parameter). At least one value is required. Accepts any value of
              `SingleThreadStatsSelectField`.

          session_id: `session_id` is the tracing project (session) UUID (required).

          filter: `filter` narrows which of the thread's traces are aggregated, using a LangSmith
              filter expression. For example: lt(start_time, "2025-01-01T00:00:00Z") or
              eq(trace_id, "0190a1b2-c3d4-7ef0-a5b6-6ea3a82e9328"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return self._get(
            path_template("/v2/threads/{thread_id}/stats", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "selects": selects,
                        "session_id": session_id,
                        "filter": filter,
                    },
                    thread_stats_params.ThreadStatsParams,
                ),
            ),
            cast_to=ThreadStats,
        )


class AsyncThreadsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncThreadsResourceWithStreamingResponse(self)

    def list_traces(
        self,
        thread_id: str,
        *,
        project_id: str,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        page_size: int | Omit = omit,
        selects: List[
            Literal[
                "THREAD_ID",
                "TRACE_ID",
                "OP",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_TOKENS",
                "START_TIME",
                "END_TIME",
                "LATENCY",
                "FIRST_TOKEN_TIME",
                "INPUTS_PREVIEW",
                "OUTPUTS_PREVIEW",
                "PROMPT_COST",
                "COMPLETION_COST",
                "TOTAL_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "NAME",
                "ERROR_PREVIEW",
            ]
        ]
        | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[ThreadTrace, AsyncItemsCursorGetPagination[ThreadTrace]]:
        """
        **Alpha:** The request and response contract may change; Retrieve all traces
        belonging to a specific thread within a project.

        Args:
          project_id: `project_id` is the tracing project UUID (required).

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Omit on
              the first request; pass the returned cursor to fetch the next page.

          filter: `filter` narrows which traces are returned for this thread, using a LangSmith
              filter expression evaluated against each root trace run. For example: eq(status,
              "success") or has(tags, "production"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          page_size: `page_size` is the maximum number of traces to return in this response. Defaults
              to 20 when omitted; must be between 1 and 100 inclusive when set.

          selects: `selects` lists which properties to include on each returned trace (repeatable
              query parameter). Accepts any value of the `ThreadTraceSelectField` enum.
              Properties not listed are omitted from each trace object; `trace_id` is always
              returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return self._get_api_list(
            path_template("/v2/threads/{thread_id}/traces", thread_id=thread_id),
            page=AsyncItemsCursorGetPagination[ThreadTrace],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "project_id": project_id,
                        "cursor": cursor,
                        "filter": filter,
                        "page_size": page_size,
                        "selects": selects,
                    },
                    thread_list_traces_params.ThreadListTracesParams,
                ),
            ),
            model=ThreadTrace,
        )

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
    ) -> AsyncPaginator[Thread, AsyncItemsCursorPostPagination[Thread]]:
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

          max_start_time: `max_start_time` is the exclusive upper bound on thread activity (RFC3339
              date-time). Defaults to now (UTC) when omitted.

          min_start_time: `min_start_time` is the inclusive lower bound on thread activity (RFC3339
              date-time). Defaults to 1 day before now (UTC) when omitted.

          page_size: `page_size` is the maximum number of threads to return in this response.
              Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
              response may contain fewer threads than `page_size` even when `next_cursor` is
              non-null.

          project_id: `project_id` is the tracing project UUID.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/threads/query",
            page=AsyncItemsCursorPostPagination[Thread],
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
            model=Thread,
            method="post",
        )

    async def stats(
        self,
        thread_id: str,
        *,
        selects: List[
            Literal[
                "TURNS",
                "FIRST_START_TIME",
                "LAST_START_TIME",
                "LAST_END_TIME",
                "LATENCY_P50",
                "LATENCY_P99",
                "PROMPT_TOKENS",
                "PROMPT_COST",
                "COMPLETION_TOKENS",
                "COMPLETION_COST",
                "TOTAL_TOKENS",
                "TOTAL_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "FEEDBACK_STATS",
            ]
        ],
        session_id: str,
        filter: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ThreadStats:
        """
        **Alpha:** The request and response contract may change; Compute aggregate stats
        for a single thread (turn count, latency percentiles, token/cost sums, and
        detail breakdowns) within a project.

        Args:
          selects: `selects` lists which aggregate stats to compute and return (repeatable query
              parameter). At least one value is required. Accepts any value of
              `SingleThreadStatsSelectField`.

          session_id: `session_id` is the tracing project (session) UUID (required).

          filter: `filter` narrows which of the thread's traces are aggregated, using a LangSmith
              filter expression. For example: lt(start_time, "2025-01-01T00:00:00Z") or
              eq(trace_id, "0190a1b2-c3d4-7ef0-a5b6-6ea3a82e9328"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return await self._get(
            path_template("/v2/threads/{thread_id}/stats", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "selects": selects,
                        "session_id": session_id,
                        "filter": filter,
                    },
                    thread_stats_params.ThreadStatsParams,
                ),
            ),
            cast_to=ThreadStats,
        )


class ThreadsResourceWithRawResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.list_traces = to_raw_response_wrapper(
            threads.list_traces,
        )
        self.query = to_raw_response_wrapper(
            threads.query,
        )
        self.stats = to_raw_response_wrapper(
            threads.stats,
        )


class AsyncThreadsResourceWithRawResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.list_traces = async_to_raw_response_wrapper(
            threads.list_traces,
        )
        self.query = async_to_raw_response_wrapper(
            threads.query,
        )
        self.stats = async_to_raw_response_wrapper(
            threads.stats,
        )


class ThreadsResourceWithStreamingResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.list_traces = to_streamed_response_wrapper(
            threads.list_traces,
        )
        self.query = to_streamed_response_wrapper(
            threads.query,
        )
        self.stats = to_streamed_response_wrapper(
            threads.stats,
        )


class AsyncThreadsResourceWithStreamingResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.list_traces = async_to_streamed_response_wrapper(
            threads.list_traces,
        )
        self.query = async_to_streamed_response_wrapper(
            threads.query,
        )
        self.stats = async_to_streamed_response_wrapper(
            threads.stats,
        )
