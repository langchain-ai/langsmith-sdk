# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.traces import run_list_params
from ...types.query_trace_response_body import QueryTraceResponseBody

__all__ = ["RunsResource", "AsyncRunsResource"]


class RunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return RunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return RunsResourceWithStreamingResponse(self)

    def list(
        self,
        trace_id: str,
        *,
        max_start_time: Union[str, datetime],
        min_start_time: Union[str, datetime],
        project_id: str,
        filter: str | Omit = omit,
        selects: List[
            Literal[
                "ID",
                "NAME",
                "RUN_TYPE",
                "STATUS",
                "START_TIME",
                "END_TIME",
                "LATENCY_SECONDS",
                "FIRST_TOKEN_TIME",
                "ERROR",
                "ERROR_PREVIEW",
                "EXTRA",
                "METADATA",
                "EVENTS",
                "INPUTS",
                "INPUTS_PREVIEW",
                "OUTPUTS",
                "OUTPUTS_PREVIEW",
                "MANIFEST",
                "PARENT_RUN_IDS",
                "PROJECT_ID",
                "TRACE_ID",
                "THREAD_ID",
                "DOTTED_ORDER",
                "IS_ROOT",
                "REFERENCE_EXAMPLE_ID",
                "REFERENCE_DATASET_ID",
                "TOTAL_TOKENS",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_COST",
                "PROMPT_COST",
                "COMPLETION_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "PRICE_MODEL_ID",
                "TAGS",
                "APP_PATH",
                "ATTACHMENTS",
                "THREAD_EVALUATION_TIME",
                "IS_IN_DATASET",
                "SHARE_URL",
                "FEEDBACK_STATS",
            ]
        ]
        | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> QueryTraceResponseBody:
        """
        **Alpha:** The request and response contract may change; Returns runs for a
        trace ID within min/max start time. Optional `filter`; repeatable `selects` to
        select fields to return.

        Args:
          max_start_time: `max_start_time` is the inclusive upper bound for run `start_time` (RFC3339
              date-time).

          min_start_time: `min_start_time` is the inclusive lower bound for run `start_time` (RFC3339
              date-time).

          project_id: `project_id` is the UUID of the tracing project that owns the trace.

          filter: `filter` narrows which runs within this trace are returned, using a LangSmith
              filter expression evaluated against each run. For example: `eq(run_type, "llm")`
              for LLM runs only, or `eq(status, "error")` for failed runs. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          selects: `selects` lists which properties to include on each returned run (repeatable
              query parameter). Accepts any value of the `RunSelectField` enum. If omitted,
              only `id` is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not trace_id:
            raise ValueError(f"Expected a non-empty value for `trace_id` but received {trace_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._get(
            path_template("/v2/traces/{trace_id}/runs", trace_id=trace_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "max_start_time": max_start_time,
                        "min_start_time": min_start_time,
                        "project_id": project_id,
                        "filter": filter,
                        "selects": selects,
                    },
                    run_list_params.RunListParams,
                ),
            ),
            cast_to=QueryTraceResponseBody,
        )


class AsyncRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncRunsResourceWithStreamingResponse(self)

    async def list(
        self,
        trace_id: str,
        *,
        max_start_time: Union[str, datetime],
        min_start_time: Union[str, datetime],
        project_id: str,
        filter: str | Omit = omit,
        selects: List[
            Literal[
                "ID",
                "NAME",
                "RUN_TYPE",
                "STATUS",
                "START_TIME",
                "END_TIME",
                "LATENCY_SECONDS",
                "FIRST_TOKEN_TIME",
                "ERROR",
                "ERROR_PREVIEW",
                "EXTRA",
                "METADATA",
                "EVENTS",
                "INPUTS",
                "INPUTS_PREVIEW",
                "OUTPUTS",
                "OUTPUTS_PREVIEW",
                "MANIFEST",
                "PARENT_RUN_IDS",
                "PROJECT_ID",
                "TRACE_ID",
                "THREAD_ID",
                "DOTTED_ORDER",
                "IS_ROOT",
                "REFERENCE_EXAMPLE_ID",
                "REFERENCE_DATASET_ID",
                "TOTAL_TOKENS",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_COST",
                "PROMPT_COST",
                "COMPLETION_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "PRICE_MODEL_ID",
                "TAGS",
                "APP_PATH",
                "ATTACHMENTS",
                "THREAD_EVALUATION_TIME",
                "IS_IN_DATASET",
                "SHARE_URL",
                "FEEDBACK_STATS",
            ]
        ]
        | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> QueryTraceResponseBody:
        """
        **Alpha:** The request and response contract may change; Returns runs for a
        trace ID within min/max start time. Optional `filter`; repeatable `selects` to
        select fields to return.

        Args:
          max_start_time: `max_start_time` is the inclusive upper bound for run `start_time` (RFC3339
              date-time).

          min_start_time: `min_start_time` is the inclusive lower bound for run `start_time` (RFC3339
              date-time).

          project_id: `project_id` is the UUID of the tracing project that owns the trace.

          filter: `filter` narrows which runs within this trace are returned, using a LangSmith
              filter expression evaluated against each run. For example: `eq(run_type, "llm")`
              for LLM runs only, or `eq(status, "error")` for failed runs. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          selects: `selects` lists which properties to include on each returned run (repeatable
              query parameter). Accepts any value of the `RunSelectField` enum. If omitted,
              only `id` is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not trace_id:
            raise ValueError(f"Expected a non-empty value for `trace_id` but received {trace_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return await self._get(
            path_template("/v2/traces/{trace_id}/runs", trace_id=trace_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "max_start_time": max_start_time,
                        "min_start_time": min_start_time,
                        "project_id": project_id,
                        "filter": filter,
                        "selects": selects,
                    },
                    run_list_params.RunListParams,
                ),
            ),
            cast_to=QueryTraceResponseBody,
        )


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.list = to_raw_response_wrapper(
            runs.list,
        )


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.list = async_to_raw_response_wrapper(
            runs.list,
        )


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.list = to_streamed_response_wrapper(
            runs.list,
        )


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.list = async_to_streamed_response_wrapper(
            runs.list,
        )
