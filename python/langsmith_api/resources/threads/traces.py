# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import path_template, maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import SyncItemsCursorGetPagination, AsyncItemsCursorGetPagination
from ..._base_client import AsyncPaginator, make_request_options
from ...types.threads import trace_list_params
from ...types.thread_trace_list_item import ThreadTraceListItem

__all__ = ["TracesResource", "AsyncTracesResource"]


class TracesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return TracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return TracesResourceWithStreamingResponse(self)

    def list(
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
    ) -> SyncItemsCursorGetPagination[ThreadTraceListItem]:
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
            page=SyncItemsCursorGetPagination[ThreadTraceListItem],
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
                    trace_list_params.TraceListParams,
                ),
            ),
            model=ThreadTraceListItem,
        )


class AsyncTracesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncTracesResourceWithStreamingResponse(self)

    def list(
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
    ) -> AsyncPaginator[ThreadTraceListItem, AsyncItemsCursorGetPagination[ThreadTraceListItem]]:
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
            page=AsyncItemsCursorGetPagination[ThreadTraceListItem],
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
                    trace_list_params.TraceListParams,
                ),
            ),
            model=ThreadTraceListItem,
        )


class TracesResourceWithRawResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

        self.list = to_raw_response_wrapper(
            traces.list,
        )


class AsyncTracesResourceWithRawResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

        self.list = async_to_raw_response_wrapper(
            traces.list,
        )


class TracesResourceWithStreamingResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

        self.list = to_streamed_response_wrapper(
            traces.list,
        )


class AsyncTracesResourceWithStreamingResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

        self.list = async_to_streamed_response_wrapper(
            traces.list,
        )
