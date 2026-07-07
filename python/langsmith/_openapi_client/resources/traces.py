# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..types import trace_query_params, trace_list_runs_params
from .._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from .._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..pagination import SyncItemsCursorPostPagination, AsyncItemsCursorPostPagination
from ..types.trace import Trace
from .._base_client import AsyncPaginator, make_request_options
from ..types.trace_list_runs_response import TraceListRunsResponse

__all__ = ["TracesResource", "AsyncTracesResource"]


class TracesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return TracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return TracesResourceWithStreamingResponse(self)

    def list_runs(
        self,
        trace_id: str,
        *,
        project_id: str,
        filter: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
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
    ) -> TraceListRunsResponse:
        """
        **Alpha:** The request and response contract may change; Returns runs for a
        trace ID within min/max start time. Optional `filter`; repeatable `selects` to
        select fields to return.

        Args:
          project_id: `project_id` is the UUID of the tracing project that owns the trace.

          filter: `filter` narrows which runs within this trace are returned, using a LangSmith
              filter expression evaluated against each run. For example: `eq(run_type, "llm")`
              for LLM runs only, or `eq(status, "error")` for failed runs. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          max_start_time: `max_start_time` is the optional inclusive upper bound for run `start_time`
              (RFC3339 date-time). Required together with `min_start_time`.

          min_start_time: `min_start_time` is the optional inclusive lower bound for run `start_time`
              (RFC3339 date-time). Required together with `max_start_time`.

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
                        "project_id": project_id,
                        "filter": filter,
                        "max_start_time": max_start_time,
                        "min_start_time": min_start_time,
                        "selects": selects,
                    },
                    trace_list_runs_params.TraceListRunsParams,
                ),
            ),
            cast_to=TraceListRunsResponse,
        )

    def query(
        self,
        *,
        cursor: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_id: str | Omit = omit,
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
        trace_filter: str | Omit = omit,
        trace_ids: SequenceNotStr[str] | Omit = omit,
        tree_filter: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorPostPagination[Trace]:
        """
        Returns a paginated list of traces (root runs) for a single tracing project.
        Each item carries the trace's root run plus optional trace-wide aggregates
        (`total_tokens`, `total_cost`, `first_token_time`) under `trace_aggregates`, so
        clients never have to merge by `trace_id`.

        Traces are scanned within a `start_time` window: `min_start_time` defaults to 24
        hours before the request, `max_start_time` defaults to the request time. Set
        either explicitly to widen or narrow the window.

        Supports filters (`trace_filter`, `tree_filter`), cursor pagination (`cursor`),
        and field projection (`selects`).

        Args:
          cursor: `cursor` is the opaque string returned in a previous response's `next_cursor`.

          max_start_time: `max_start_time` is the exclusive upper bound for the root-run start time scan
              (RFC3339). Defaults to the request time when omitted.

          min_start_time: `min_start_time` is the inclusive lower bound for the root-run start time scan
              (RFC3339). Defaults to 24 hours before the request when omitted.

          page_size: `page_size` is the maximum number of traces to return per page. Defaults to 20;
              must be between 1 and 100 when set.

          project_id: `project_id` is the UUID of the tracing project that owns the traces. Required.

          selects: `selects` lists which properties to include on each returned trace. Properties
              listed here are routed to the appropriate sub-object on each item:
              `total_tokens`, `total_cost`, and `first_token_time` appear under
              `trace_aggregates`; everything else appears under `root_run`. If omitted, only
              `id` is returned on `root_run`.

          trace_filter: `trace_filter` narrows results to traces whose root run matches this LangSmith
              filter expression. This filter targets root runs only — `is_root = true` is
              implied. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          trace_ids: `trace_ids` is an optional fast-path restriction to a known set of trace UUIDs.
              Equivalent in result to including each UUID in a `trace_filter`, but more
              efficient at scale.

          tree_filter: `tree_filter` narrows results to traces containing at least one run anywhere in
              the run tree (root or descendant) that matches this LangSmith filter expression.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/traces/query",
            page=SyncItemsCursorPostPagination[Trace],
            body=maybe_transform(
                {
                    "cursor": cursor,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_id": project_id,
                    "selects": selects,
                    "trace_filter": trace_filter,
                    "trace_ids": trace_ids,
                    "tree_filter": tree_filter,
                },
                trace_query_params.TraceQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=Trace,
            method="post",
        )


class AsyncTracesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return AsyncTracesResourceWithStreamingResponse(self)

    async def list_runs(
        self,
        trace_id: str,
        *,
        project_id: str,
        filter: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
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
    ) -> TraceListRunsResponse:
        """
        **Alpha:** The request and response contract may change; Returns runs for a
        trace ID within min/max start time. Optional `filter`; repeatable `selects` to
        select fields to return.

        Args:
          project_id: `project_id` is the UUID of the tracing project that owns the trace.

          filter: `filter` narrows which runs within this trace are returned, using a LangSmith
              filter expression evaluated against each run. For example: `eq(run_type, "llm")`
              for LLM runs only, or `eq(status, "error")` for failed runs. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          max_start_time: `max_start_time` is the optional inclusive upper bound for run `start_time`
              (RFC3339 date-time). Required together with `min_start_time`.

          min_start_time: `min_start_time` is the optional inclusive lower bound for run `start_time`
              (RFC3339 date-time). Required together with `max_start_time`.

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
                        "project_id": project_id,
                        "filter": filter,
                        "max_start_time": max_start_time,
                        "min_start_time": min_start_time,
                        "selects": selects,
                    },
                    trace_list_runs_params.TraceListRunsParams,
                ),
            ),
            cast_to=TraceListRunsResponse,
        )

    def query(
        self,
        *,
        cursor: str | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_id: str | Omit = omit,
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
        trace_filter: str | Omit = omit,
        trace_ids: SequenceNotStr[str] | Omit = omit,
        tree_filter: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[Trace, AsyncItemsCursorPostPagination[Trace]]:
        """
        Returns a paginated list of traces (root runs) for a single tracing project.
        Each item carries the trace's root run plus optional trace-wide aggregates
        (`total_tokens`, `total_cost`, `first_token_time`) under `trace_aggregates`, so
        clients never have to merge by `trace_id`.

        Traces are scanned within a `start_time` window: `min_start_time` defaults to 24
        hours before the request, `max_start_time` defaults to the request time. Set
        either explicitly to widen or narrow the window.

        Supports filters (`trace_filter`, `tree_filter`), cursor pagination (`cursor`),
        and field projection (`selects`).

        Args:
          cursor: `cursor` is the opaque string returned in a previous response's `next_cursor`.

          max_start_time: `max_start_time` is the exclusive upper bound for the root-run start time scan
              (RFC3339). Defaults to the request time when omitted.

          min_start_time: `min_start_time` is the inclusive lower bound for the root-run start time scan
              (RFC3339). Defaults to 24 hours before the request when omitted.

          page_size: `page_size` is the maximum number of traces to return per page. Defaults to 20;
              must be between 1 and 100 when set.

          project_id: `project_id` is the UUID of the tracing project that owns the traces. Required.

          selects: `selects` lists which properties to include on each returned trace. Properties
              listed here are routed to the appropriate sub-object on each item:
              `total_tokens`, `total_cost`, and `first_token_time` appear under
              `trace_aggregates`; everything else appears under `root_run`. If omitted, only
              `id` is returned on `root_run`.

          trace_filter: `trace_filter` narrows results to traces whose root run matches this LangSmith
              filter expression. This filter targets root runs only — `is_root = true` is
              implied. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          trace_ids: `trace_ids` is an optional fast-path restriction to a known set of trace UUIDs.
              Equivalent in result to including each UUID in a `trace_filter`, but more
              efficient at scale.

          tree_filter: `tree_filter` narrows results to traces containing at least one run anywhere in
              the run tree (root or descendant) that matches this LangSmith filter expression.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v2/traces/query",
            page=AsyncItemsCursorPostPagination[Trace],
            body=maybe_transform(
                {
                    "cursor": cursor,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_id": project_id,
                    "selects": selects,
                    "trace_filter": trace_filter,
                    "trace_ids": trace_ids,
                    "tree_filter": tree_filter,
                },
                trace_query_params.TraceQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=Trace,
            method="post",
        )


class TracesResourceWithRawResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

        self.list_runs = to_raw_response_wrapper(
            traces.list_runs,
        )
        self.query = to_raw_response_wrapper(
            traces.query,
        )


class AsyncTracesResourceWithRawResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

        self.list_runs = async_to_raw_response_wrapper(
            traces.list_runs,
        )
        self.query = async_to_raw_response_wrapper(
            traces.query,
        )


class TracesResourceWithStreamingResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

        self.list_runs = to_streamed_response_wrapper(
            traces.list_runs,
        )
        self.query = to_streamed_response_wrapper(
            traces.query,
        )


class AsyncTracesResourceWithStreamingResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

        self.list_runs = async_to_streamed_response_wrapper(
            traces.list_runs,
        )
        self.query = async_to_streamed_response_wrapper(
            traces.query,
        )
