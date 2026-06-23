# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..types import run_query_v2_params, run_retrieve_v2_params
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
from .._base_client import AsyncPaginator, make_request_options
from ..types.query_run_response import QueryRunResponse

__all__ = ["RunsResource", "AsyncRunsResource"]


class RunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return RunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return RunsResourceWithStreamingResponse(self)

    def query_v2(
        self,
        *,
        ai_query: str | Omit = omit,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        has_error: bool | Omit = omit,
        ids: SequenceNotStr[str] | Omit = omit,
        is_root: bool | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_ids: SequenceNotStr[str] | Omit = omit,
        reference_dataset_id: str | Omit = omit,
        reference_examples: SequenceNotStr[str] | Omit = omit,
        run_type: Literal["TOOL", "CHAIN", "LLM", "RETRIEVER", "EMBEDDING", "PROMPT", "PARSER"] | Omit = omit,
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
        sort_order: Literal["ASC", "DESC"] | Omit = omit,
        trace_filter: str | Omit = omit,
        trace_id: str | Omit = omit,
        tree_filter: str | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorPostPagination[QueryRunResponse]:
        """
        **Alpha:** The request and response contract may change; Returns a paginated
        list of runs for the given projects within min/max start_time. Supports filters,
        cursor pagination, and `selects` to select fields to return.

        Args:
          ai_query: `ai_query` is a natural-language query to filter runs using AI.

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Treat it
              as opaque and pass it back unmodified.

          filter: `filter` narrows results to runs matching this LangSmith filter expression,
              evaluated against each individual run. For example: and(eq(run_type, "llm"),
              gt(latency, 5)) or eq(status, "error"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          has_error: `has_error` filters to runs that errored (true) or completed without error
              (false).

          ids: `ids` optionally limits the request to these run UUIDs.

          is_root: `is_root` returns only root runs (true) or only non-root runs (false).

          max_start_time: `max_start_time` is the upper bound for run `start_time` (RFC3339). Defaults to
              now.

          min_start_time: `min_start_time` is the lower bound for run `start_time` (RFC3339). Defaults to
              1 day ago.

          page_size: `page_size` is the maximum number of runs to return in this response. Defaults
              to 100 when omitted; must be between 1 and 1000 inclusive when set.

          project_ids: `project_ids` lists tracing project UUIDs to query. Required unless
              `reference_dataset_id` is set. Mutually exclusive with `reference_dataset_id` —
              set exactly one of them.

          reference_dataset_id: `reference_dataset_id` resolves session IDs server-side from the dataset.
              Required unless `project_ids` is set. Mutually exclusive with `project_ids` —
              set exactly one of them. When provided and `min_start_time` is omitted, the
              server derives it from the earliest session creation date.

          reference_examples: `reference_examples` optionally limits to runs linked to these dataset example
              UUIDs.

          run_type: `run_type`, when set, restricts results to runs whose `run_type` equals this
              value.

          selects: `selects` lists which properties to include on each returned run. If omitted,
              only `id` is returned. Properties not listed are omitted from each run object.

          sort_order: `sort_order` is the sort direction for `start_time` (`ASC` or `DESC`). Defaults
              to `DESC` when omitted. Maps to the SmithDB proto `Order` field.

          trace_filter: `trace_filter` narrows results to runs whose root trace matches this LangSmith
              filter expression. Use this to filter by properties of the trace's root run —
              for example eq(status, "success") to include only traces that completed without
              error. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          trace_id: `trace_id` optionally limits results to runs belonging to this trace UUID.

          tree_filter: `tree_filter` narrows results to runs that belong to a trace containing at least
              one run matching this LangSmith filter expression anywhere in the run tree (not
              just the root). Use this to find runs inside traces that involved a specific
              tool, tag, or model — for example has(tags, "production") or eq(name,
              "my_tool"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            "/v2/runs/query",
            page=SyncItemsCursorPostPagination[QueryRunResponse],
            body=maybe_transform(
                {
                    "ai_query": ai_query,
                    "cursor": cursor,
                    "filter": filter,
                    "has_error": has_error,
                    "ids": ids,
                    "is_root": is_root,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_ids": project_ids,
                    "reference_dataset_id": reference_dataset_id,
                    "reference_examples": reference_examples,
                    "run_type": run_type,
                    "selects": selects,
                    "sort_order": sort_order,
                    "trace_filter": trace_filter,
                    "trace_id": trace_id,
                    "tree_filter": tree_filter,
                },
                run_query_v2_params.RunQueryV2Params,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=QueryRunResponse,
            method="post",
        )

    def retrieve_v2(
        self,
        run_id: str,
        *,
        project_id: str,
        start_time: Union[str, datetime],
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
    ) -> QueryRunResponse:
        """
        **Alpha:** The request and response contract may change; Returns one run by ID
        for the given session and start_time. Use the `selects` query parameter
        (repeatable) to select fields to return.

        Args:
          project_id: `project_id` is the UUID of the tracing project that owns the run.

          start_time: `start_time` is the run's `start_time` (RFC3339 date-time), used together with
              `project_id` to locate the run.

          selects: `selects` lists which properties to include on the returned run (repeatable
              query parameter). Accepts any value of the `RunSelectField` enum. If omitted,
              only `id` is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._get(
            path_template("/v2/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "project_id": project_id,
                        "start_time": start_time,
                        "selects": selects,
                    },
                    run_retrieve_v2_params.RunRetrieveV2Params,
                ),
            ),
            cast_to=QueryRunResponse,
        )

    retrieve = retrieve_v2

    query = query_v2


class AsyncRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return AsyncRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return AsyncRunsResourceWithStreamingResponse(self)

    def query_v2(
        self,
        *,
        ai_query: str | Omit = omit,
        cursor: str | Omit = omit,
        filter: str | Omit = omit,
        has_error: bool | Omit = omit,
        ids: SequenceNotStr[str] | Omit = omit,
        is_root: bool | Omit = omit,
        max_start_time: Union[str, datetime] | Omit = omit,
        min_start_time: Union[str, datetime] | Omit = omit,
        page_size: int | Omit = omit,
        project_ids: SequenceNotStr[str] | Omit = omit,
        reference_dataset_id: str | Omit = omit,
        reference_examples: SequenceNotStr[str] | Omit = omit,
        run_type: Literal["TOOL", "CHAIN", "LLM", "RETRIEVER", "EMBEDDING", "PROMPT", "PARSER"] | Omit = omit,
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
        sort_order: Literal["ASC", "DESC"] | Omit = omit,
        trace_filter: str | Omit = omit,
        trace_id: str | Omit = omit,
        tree_filter: str | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[QueryRunResponse, AsyncItemsCursorPostPagination[QueryRunResponse]]:
        """
        **Alpha:** The request and response contract may change; Returns a paginated
        list of runs for the given projects within min/max start_time. Supports filters,
        cursor pagination, and `selects` to select fields to return.

        Args:
          ai_query: `ai_query` is a natural-language query to filter runs using AI.

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Treat it
              as opaque and pass it back unmodified.

          filter: `filter` narrows results to runs matching this LangSmith filter expression,
              evaluated against each individual run. For example: and(eq(run_type, "llm"),
              gt(latency, 5)) or eq(status, "error"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          has_error: `has_error` filters to runs that errored (true) or completed without error
              (false).

          ids: `ids` optionally limits the request to these run UUIDs.

          is_root: `is_root` returns only root runs (true) or only non-root runs (false).

          max_start_time: `max_start_time` is the upper bound for run `start_time` (RFC3339). Defaults to
              now.

          min_start_time: `min_start_time` is the lower bound for run `start_time` (RFC3339). Defaults to
              1 day ago.

          page_size: `page_size` is the maximum number of runs to return in this response. Defaults
              to 100 when omitted; must be between 1 and 1000 inclusive when set.

          project_ids: `project_ids` lists tracing project UUIDs to query. Required unless
              `reference_dataset_id` is set. Mutually exclusive with `reference_dataset_id` —
              set exactly one of them.

          reference_dataset_id: `reference_dataset_id` resolves session IDs server-side from the dataset.
              Required unless `project_ids` is set. Mutually exclusive with `project_ids` —
              set exactly one of them. When provided and `min_start_time` is omitted, the
              server derives it from the earliest session creation date.

          reference_examples: `reference_examples` optionally limits to runs linked to these dataset example
              UUIDs.

          run_type: `run_type`, when set, restricts results to runs whose `run_type` equals this
              value.

          selects: `selects` lists which properties to include on each returned run. If omitted,
              only `id` is returned. Properties not listed are omitted from each run object.

          sort_order: `sort_order` is the sort direction for `start_time` (`ASC` or `DESC`). Defaults
              to `DESC` when omitted. Maps to the SmithDB proto `Order` field.

          trace_filter: `trace_filter` narrows results to runs whose root trace matches this LangSmith
              filter expression. Use this to filter by properties of the trace's root run —
              for example eq(status, "success") to include only traces that completed without
              error. See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          trace_id: `trace_id` optionally limits results to runs belonging to this trace UUID.

          tree_filter: `tree_filter` narrows results to runs that belong to a trace containing at least
              one run matching this LangSmith filter expression anywhere in the run tree (not
              just the root). Use this to find runs inside traces that involved a specific
              tool, tag, or model — for example has(tags, "production") or eq(name,
              "my_tool"). See
              https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
              for syntax.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            "/v2/runs/query",
            page=AsyncItemsCursorPostPagination[QueryRunResponse],
            body=maybe_transform(
                {
                    "ai_query": ai_query,
                    "cursor": cursor,
                    "filter": filter,
                    "has_error": has_error,
                    "ids": ids,
                    "is_root": is_root,
                    "max_start_time": max_start_time,
                    "min_start_time": min_start_time,
                    "page_size": page_size,
                    "project_ids": project_ids,
                    "reference_dataset_id": reference_dataset_id,
                    "reference_examples": reference_examples,
                    "run_type": run_type,
                    "selects": selects,
                    "sort_order": sort_order,
                    "trace_filter": trace_filter,
                    "trace_id": trace_id,
                    "tree_filter": tree_filter,
                },
                run_query_v2_params.RunQueryV2Params,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=QueryRunResponse,
            method="post",
        )

    async def retrieve_v2(
        self,
        run_id: str,
        *,
        project_id: str,
        start_time: Union[str, datetime],
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
    ) -> QueryRunResponse:
        """
        **Alpha:** The request and response contract may change; Returns one run by ID
        for the given session and start_time. Use the `selects` query parameter
        (repeatable) to select fields to return.

        Args:
          project_id: `project_id` is the UUID of the tracing project that owns the run.

          start_time: `start_time` is the run's `start_time` (RFC3339 date-time), used together with
              `project_id` to locate the run.

          selects: `selects` lists which properties to include on the returned run (repeatable
              query parameter). Accepts any value of the `RunSelectField` enum. If omitted,
              only `id` is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return await self._get(
            path_template("/v2/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "project_id": project_id,
                        "start_time": start_time,
                        "selects": selects,
                    },
                    run_retrieve_v2_params.RunRetrieveV2Params,
                ),
            ),
            cast_to=QueryRunResponse,
        )

    retrieve = retrieve_v2

    query = query_v2


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.query_v2 = to_raw_response_wrapper(
            runs.query_v2,
        )
        self.retrieve_v2 = to_raw_response_wrapper(
            runs.retrieve_v2,
        )
        self.retrieve = to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = to_raw_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.query_v2 = async_to_raw_response_wrapper(
            runs.query_v2,
        )
        self.retrieve_v2 = async_to_raw_response_wrapper(
            runs.retrieve_v2,
        )
        self.retrieve = async_to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_raw_response_wrapper(
            runs.query,
        )


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.query_v2 = to_streamed_response_wrapper(
            runs.query_v2,
        )
        self.retrieve_v2 = to_streamed_response_wrapper(
            runs.retrieve_v2,
        )
        self.retrieve = to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = to_streamed_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.query_v2 = async_to_streamed_response_wrapper(
            runs.query_v2,
        )
        self.retrieve_v2 = async_to_streamed_response_wrapper(
            runs.retrieve_v2,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_streamed_response_wrapper(
            runs.query,
        )
