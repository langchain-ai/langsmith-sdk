# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import typing_extensions
from typing import Any, List, Union, Optional, cast
from datetime import datetime
from typing_extensions import Literal

import httpx

from .share import (
    ShareResource,
    AsyncShareResource,
    ShareResourceWithRawResponse,
    AsyncShareResourceWithRawResponse,
    ShareResourceWithStreamingResponse,
    AsyncShareResourceWithStreamingResponse,
)
from ...types import (
    RunTypeEnum,
    RunsFilterDataSourceTypeEnum,
    run_query_params,
    run_stats_params,
    run_retrieve_params,
    run_query_legacy_params,
    run_retrieve_legacy_params,
)
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import (
    SyncCursorPagination,
    AsyncCursorPagination,
    SyncItemsCursorPostPagination,
    AsyncItemsCursorPostPagination,
)
from ..._base_client import AsyncPaginator, make_request_options
from ...types.run_schema import RunSchema
from ...types.run_type_enum import RunTypeEnum
from ...types.query_run_response import QueryRunResponse
from ...types.run_stats_response import RunStatsResponse
from ...types.run_stats_group_by_param import RunStatsGroupByParam
from ...types.runs_filter_data_source_type_enum import RunsFilterDataSourceTypeEnum

__all__ = ["RunsResource", "AsyncRunsResource"]


class RunsResource(SyncAPIResource):
    @cached_property
    def share(self) -> ShareResource:
        return ShareResource(self._client)

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

    def retrieve(
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
                    run_retrieve_params.RunRetrieveParams,
                ),
            ),
            cast_to=QueryRunResponse,
        )

    def query(
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

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`.

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

          project_ids: `project_ids` lists tracing project UUIDs to query.

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
                    "reference_examples": reference_examples,
                    "run_type": run_type,
                    "selects": selects,
                    "sort_order": sort_order,
                    "trace_filter": trace_filter,
                    "trace_id": trace_id,
                    "tree_filter": tree_filter,
                },
                run_query_params.RunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=QueryRunResponse,
            method="post",
        )

    @typing_extensions.deprecated("Use query instead (POST /v2/runs/query).")
    def query_legacy(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        cursor: Optional[str] | Omit = omit,
        data_source_type: Optional[RunsFilterDataSourceTypeEnum] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        execution_order: Optional[int] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        is_root: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        order: Literal["asc", "desc"] | Omit = omit,
        parent_run: Optional[str] | Omit = omit,
        query: Optional[str] | Omit = omit,
        reference_example: Optional[SequenceNotStr[str]] | Omit = omit,
        run_type: Optional[RunTypeEnum] | Omit = omit,
        search_filter: Optional[str] | Omit = omit,
        select: List[
            Literal[
                "id",
                "name",
                "run_type",
                "start_time",
                "end_time",
                "status",
                "error",
                "extra",
                "events",
                "inputs",
                "inputs_preview",
                "inputs_s3_urls",
                "inputs_or_signed_url",
                "outputs",
                "outputs_preview",
                "outputs_s3_urls",
                "outputs_or_signed_url",
                "s3_urls",
                "error_or_signed_url",
                "events_or_signed_url",
                "extra_or_signed_url",
                "serialized_or_signed_url",
                "parent_run_id",
                "manifest_id",
                "manifest_s3_id",
                "manifest",
                "session_id",
                "serialized",
                "reference_example_id",
                "reference_dataset_id",
                "total_tokens",
                "prompt_tokens",
                "prompt_token_details",
                "completion_tokens",
                "completion_token_details",
                "total_cost",
                "prompt_cost",
                "prompt_cost_details",
                "completion_cost",
                "completion_cost_details",
                "price_model_id",
                "first_token_time",
                "trace_id",
                "dotted_order",
                "last_queued_at",
                "feedback_stats",
                "child_run_ids",
                "parent_run_ids",
                "tags",
                "in_dataset",
                "app_path",
                "share_token",
                "trace_tier",
                "trace_first_received_at",
                "ttl_seconds",
                "trace_upgrade",
                "thread_id",
                "trace_min_max_start_time",
                "messages",
                "inserted_at",
            ]
        ]
        | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
        skip_pagination: Optional[bool] | Omit = omit,
        skip_prev_cursor: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace: Optional[str] | Omit = omit,
        trace_filter: Optional[str] | Omit = omit,
        tree_filter: Optional[str] | Omit = omit,
        use_experimental_search: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncCursorPagination[RunSchema]:
        """
        Query Runs

        Args:
          data_source_type: Enum for run data source types.

          order: Enum for run start date order.

          run_type: Enum for run types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/runs/query",
            page=SyncCursorPagination[RunSchema],
            body=maybe_transform(
                {
                    "id": id,
                    "cursor": cursor,
                    "data_source_type": data_source_type,
                    "end_time": end_time,
                    "error": error,
                    "execution_order": execution_order,
                    "filter": filter,
                    "is_root": is_root,
                    "limit": limit,
                    "order": order,
                    "parent_run": parent_run,
                    "query": query,
                    "reference_example": reference_example,
                    "run_type": run_type,
                    "search_filter": search_filter,
                    "select": select,
                    "session": session,
                    "skip_pagination": skip_pagination,
                    "skip_prev_cursor": skip_prev_cursor,
                    "start_time": start_time,
                    "trace": trace,
                    "trace_filter": trace_filter,
                    "tree_filter": tree_filter,
                    "use_experimental_search": use_experimental_search,
                },
                run_query_legacy_params.RunQueryLegacyParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=RunSchema,
            method="post",
        )

    @typing_extensions.deprecated("Use retrieve instead (GET /v2/runs/{run_id}).")
    def retrieve_legacy(
        self,
        run_id: str,
        *,
        exclude_s3_stored_attributes: bool | Omit = omit,
        exclude_serialized: bool | Omit = omit,
        include_messages: bool | Omit = omit,
        session_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunSchema:
        """
        Get a specific run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return self._get(
            path_template("/api/v1/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "exclude_s3_stored_attributes": exclude_s3_stored_attributes,
                        "exclude_serialized": exclude_serialized,
                        "include_messages": include_messages,
                        "session_id": session_id,
                        "start_time": start_time,
                    },
                    run_retrieve_legacy_params.RunRetrieveLegacyParams,
                ),
            ),
            cast_to=RunSchema,
        )

    def stats(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        data_source_type: Optional[RunsFilterDataSourceTypeEnum] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        execution_order: Optional[int] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        group_by: Optional[RunStatsGroupByParam] | Omit = omit,
        groups: Optional[SequenceNotStr[Optional[str]]] | Omit = omit,
        is_root: Optional[bool] | Omit = omit,
        parent_run: Optional[str] | Omit = omit,
        query: Optional[str] | Omit = omit,
        reference_example: Optional[SequenceNotStr[str]] | Omit = omit,
        run_type: Optional[RunTypeEnum] | Omit = omit,
        search_filter: Optional[str] | Omit = omit,
        select: Optional[
            List[
                Literal[
                    "run_count",
                    "latency_p50",
                    "latency_p99",
                    "latency_avg",
                    "first_token_p50",
                    "first_token_p99",
                    "total_tokens",
                    "prompt_tokens",
                    "completion_tokens",
                    "median_tokens",
                    "completion_tokens_p50",
                    "prompt_tokens_p50",
                    "tokens_p99",
                    "completion_tokens_p99",
                    "prompt_tokens_p99",
                    "last_run_start_time",
                    "feedback_stats",
                    "thread_feedback_stats",
                    "run_facets",
                    "error_rate",
                    "streaming_rate",
                    "total_cost",
                    "prompt_cost",
                    "completion_cost",
                    "cost_p50",
                    "cost_p99",
                    "session_feedback_stats",
                    "all_run_stats",
                    "all_token_stats",
                    "prompt_token_details",
                    "completion_token_details",
                    "prompt_cost_details",
                    "completion_cost_details",
                ]
            ]
        ]
        | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
        skip_pagination: Optional[bool] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace: Optional[str] | Omit = omit,
        trace_filter: Optional[str] | Omit = omit,
        tree_filter: Optional[str] | Omit = omit,
        use_experimental_search: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunStatsResponse:
        """
        Get all runs by query in body payload.

        Args:
          data_source_type: Enum for run data source types.

          group_by: Group by param for run stats.

          run_type: Enum for run types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return cast(
            RunStatsResponse,
            self._post(
                "/api/v1/runs/stats",
                body=maybe_transform(
                    {
                        "id": id,
                        "data_source_type": data_source_type,
                        "end_time": end_time,
                        "error": error,
                        "execution_order": execution_order,
                        "filter": filter,
                        "group_by": group_by,
                        "groups": groups,
                        "is_root": is_root,
                        "parent_run": parent_run,
                        "query": query,
                        "reference_example": reference_example,
                        "run_type": run_type,
                        "search_filter": search_filter,
                        "select": select,
                        "session": session,
                        "skip_pagination": skip_pagination,
                        "start_time": start_time,
                        "trace": trace,
                        "trace_filter": trace_filter,
                        "tree_filter": tree_filter,
                        "use_experimental_search": use_experimental_search,
                    },
                    run_stats_params.RunStatsParams,
                ),
                options=make_request_options(
                    extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
                ),
                cast_to=cast(Any, RunStatsResponse),  # Union types cannot be passed in as arguments in the type system
            ),
        )

    def update_2(
        self,
        run_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update a run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return self._patch(
            path_template("/api/v1/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncRunsResource(AsyncAPIResource):
    @cached_property
    def share(self) -> AsyncShareResource:
        return AsyncShareResource(self._client)

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

    async def retrieve(
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
                    run_retrieve_params.RunRetrieveParams,
                ),
            ),
            cast_to=QueryRunResponse,
        )

    def query(
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

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`.

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

          project_ids: `project_ids` lists tracing project UUIDs to query.

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
                    "reference_examples": reference_examples,
                    "run_type": run_type,
                    "selects": selects,
                    "sort_order": sort_order,
                    "trace_filter": trace_filter,
                    "trace_id": trace_id,
                    "tree_filter": tree_filter,
                },
                run_query_params.RunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=QueryRunResponse,
            method="post",
        )

    @typing_extensions.deprecated("Use query instead (POST /v2/runs/query).")
    def query_legacy(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        cursor: Optional[str] | Omit = omit,
        data_source_type: Optional[RunsFilterDataSourceTypeEnum] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        execution_order: Optional[int] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        is_root: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        order: Literal["asc", "desc"] | Omit = omit,
        parent_run: Optional[str] | Omit = omit,
        query: Optional[str] | Omit = omit,
        reference_example: Optional[SequenceNotStr[str]] | Omit = omit,
        run_type: Optional[RunTypeEnum] | Omit = omit,
        search_filter: Optional[str] | Omit = omit,
        select: List[
            Literal[
                "id",
                "name",
                "run_type",
                "start_time",
                "end_time",
                "status",
                "error",
                "extra",
                "events",
                "inputs",
                "inputs_preview",
                "inputs_s3_urls",
                "inputs_or_signed_url",
                "outputs",
                "outputs_preview",
                "outputs_s3_urls",
                "outputs_or_signed_url",
                "s3_urls",
                "error_or_signed_url",
                "events_or_signed_url",
                "extra_or_signed_url",
                "serialized_or_signed_url",
                "parent_run_id",
                "manifest_id",
                "manifest_s3_id",
                "manifest",
                "session_id",
                "serialized",
                "reference_example_id",
                "reference_dataset_id",
                "total_tokens",
                "prompt_tokens",
                "prompt_token_details",
                "completion_tokens",
                "completion_token_details",
                "total_cost",
                "prompt_cost",
                "prompt_cost_details",
                "completion_cost",
                "completion_cost_details",
                "price_model_id",
                "first_token_time",
                "trace_id",
                "dotted_order",
                "last_queued_at",
                "feedback_stats",
                "child_run_ids",
                "parent_run_ids",
                "tags",
                "in_dataset",
                "app_path",
                "share_token",
                "trace_tier",
                "trace_first_received_at",
                "ttl_seconds",
                "trace_upgrade",
                "thread_id",
                "trace_min_max_start_time",
                "messages",
                "inserted_at",
            ]
        ]
        | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
        skip_pagination: Optional[bool] | Omit = omit,
        skip_prev_cursor: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace: Optional[str] | Omit = omit,
        trace_filter: Optional[str] | Omit = omit,
        tree_filter: Optional[str] | Omit = omit,
        use_experimental_search: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[RunSchema, AsyncCursorPagination[RunSchema]]:
        """
        Query Runs

        Args:
          data_source_type: Enum for run data source types.

          order: Enum for run start date order.

          run_type: Enum for run types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/runs/query",
            page=AsyncCursorPagination[RunSchema],
            body=maybe_transform(
                {
                    "id": id,
                    "cursor": cursor,
                    "data_source_type": data_source_type,
                    "end_time": end_time,
                    "error": error,
                    "execution_order": execution_order,
                    "filter": filter,
                    "is_root": is_root,
                    "limit": limit,
                    "order": order,
                    "parent_run": parent_run,
                    "query": query,
                    "reference_example": reference_example,
                    "run_type": run_type,
                    "search_filter": search_filter,
                    "select": select,
                    "session": session,
                    "skip_pagination": skip_pagination,
                    "skip_prev_cursor": skip_prev_cursor,
                    "start_time": start_time,
                    "trace": trace,
                    "trace_filter": trace_filter,
                    "tree_filter": tree_filter,
                    "use_experimental_search": use_experimental_search,
                },
                run_query_legacy_params.RunQueryLegacyParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=RunSchema,
            method="post",
        )

    @typing_extensions.deprecated("Use retrieve instead (GET /v2/runs/{run_id}).")
    async def retrieve_legacy(
        self,
        run_id: str,
        *,
        exclude_s3_stored_attributes: bool | Omit = omit,
        exclude_serialized: bool | Omit = omit,
        include_messages: bool | Omit = omit,
        session_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunSchema:
        """
        Get a specific run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return await self._get(
            path_template("/api/v1/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "exclude_s3_stored_attributes": exclude_s3_stored_attributes,
                        "exclude_serialized": exclude_serialized,
                        "include_messages": include_messages,
                        "session_id": session_id,
                        "start_time": start_time,
                    },
                    run_retrieve_legacy_params.RunRetrieveLegacyParams,
                ),
            ),
            cast_to=RunSchema,
        )

    async def stats(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        data_source_type: Optional[RunsFilterDataSourceTypeEnum] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        execution_order: Optional[int] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        group_by: Optional[RunStatsGroupByParam] | Omit = omit,
        groups: Optional[SequenceNotStr[Optional[str]]] | Omit = omit,
        is_root: Optional[bool] | Omit = omit,
        parent_run: Optional[str] | Omit = omit,
        query: Optional[str] | Omit = omit,
        reference_example: Optional[SequenceNotStr[str]] | Omit = omit,
        run_type: Optional[RunTypeEnum] | Omit = omit,
        search_filter: Optional[str] | Omit = omit,
        select: Optional[
            List[
                Literal[
                    "run_count",
                    "latency_p50",
                    "latency_p99",
                    "latency_avg",
                    "first_token_p50",
                    "first_token_p99",
                    "total_tokens",
                    "prompt_tokens",
                    "completion_tokens",
                    "median_tokens",
                    "completion_tokens_p50",
                    "prompt_tokens_p50",
                    "tokens_p99",
                    "completion_tokens_p99",
                    "prompt_tokens_p99",
                    "last_run_start_time",
                    "feedback_stats",
                    "thread_feedback_stats",
                    "run_facets",
                    "error_rate",
                    "streaming_rate",
                    "total_cost",
                    "prompt_cost",
                    "completion_cost",
                    "cost_p50",
                    "cost_p99",
                    "session_feedback_stats",
                    "all_run_stats",
                    "all_token_stats",
                    "prompt_token_details",
                    "completion_token_details",
                    "prompt_cost_details",
                    "completion_cost_details",
                ]
            ]
        ]
        | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
        skip_pagination: Optional[bool] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace: Optional[str] | Omit = omit,
        trace_filter: Optional[str] | Omit = omit,
        tree_filter: Optional[str] | Omit = omit,
        use_experimental_search: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunStatsResponse:
        """
        Get all runs by query in body payload.

        Args:
          data_source_type: Enum for run data source types.

          group_by: Group by param for run stats.

          run_type: Enum for run types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return cast(
            RunStatsResponse,
            await self._post(
                "/api/v1/runs/stats",
                body=await async_maybe_transform(
                    {
                        "id": id,
                        "data_source_type": data_source_type,
                        "end_time": end_time,
                        "error": error,
                        "execution_order": execution_order,
                        "filter": filter,
                        "group_by": group_by,
                        "groups": groups,
                        "is_root": is_root,
                        "parent_run": parent_run,
                        "query": query,
                        "reference_example": reference_example,
                        "run_type": run_type,
                        "search_filter": search_filter,
                        "select": select,
                        "session": session,
                        "skip_pagination": skip_pagination,
                        "start_time": start_time,
                        "trace": trace,
                        "trace_filter": trace_filter,
                        "tree_filter": tree_filter,
                        "use_experimental_search": use_experimental_search,
                    },
                    run_stats_params.RunStatsParams,
                ),
                options=make_request_options(
                    extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
                ),
                cast_to=cast(Any, RunStatsResponse),  # Union types cannot be passed in as arguments in the type system
            ),
        )

    async def update_2(
        self,
        run_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update a run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return await self._patch(
            path_template("/api/v1/runs/{run_id}", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.retrieve = to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = to_raw_response_wrapper(
            runs.query,
        )
        self.query_legacy = (  # pyright: ignore[reportDeprecated]
            to_raw_response_wrapper(
                runs.query_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.retrieve_legacy = (  # pyright: ignore[reportDeprecated]
            to_raw_response_wrapper(
                runs.retrieve_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.stats = to_raw_response_wrapper(
            runs.stats,
        )
        self.update_2 = to_raw_response_wrapper(
            runs.update_2,
        )

    @cached_property
    def share(self) -> ShareResourceWithRawResponse:
        return ShareResourceWithRawResponse(self._runs.share)


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.retrieve = async_to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_raw_response_wrapper(
            runs.query,
        )
        self.query_legacy = (  # pyright: ignore[reportDeprecated]
            async_to_raw_response_wrapper(
                runs.query_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.retrieve_legacy = (  # pyright: ignore[reportDeprecated]
            async_to_raw_response_wrapper(
                runs.retrieve_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.stats = async_to_raw_response_wrapper(
            runs.stats,
        )
        self.update_2 = async_to_raw_response_wrapper(
            runs.update_2,
        )

    @cached_property
    def share(self) -> AsyncShareResourceWithRawResponse:
        return AsyncShareResourceWithRawResponse(self._runs.share)


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.retrieve = to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = to_streamed_response_wrapper(
            runs.query,
        )
        self.query_legacy = (  # pyright: ignore[reportDeprecated]
            to_streamed_response_wrapper(
                runs.query_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.retrieve_legacy = (  # pyright: ignore[reportDeprecated]
            to_streamed_response_wrapper(
                runs.retrieve_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.stats = to_streamed_response_wrapper(
            runs.stats,
        )
        self.update_2 = to_streamed_response_wrapper(
            runs.update_2,
        )

    @cached_property
    def share(self) -> ShareResourceWithStreamingResponse:
        return ShareResourceWithStreamingResponse(self._runs.share)


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.retrieve = async_to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_streamed_response_wrapper(
            runs.query,
        )
        self.query_legacy = (  # pyright: ignore[reportDeprecated]
            async_to_streamed_response_wrapper(
                runs.query_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.retrieve_legacy = (  # pyright: ignore[reportDeprecated]
            async_to_streamed_response_wrapper(
                runs.retrieve_legacy,  # pyright: ignore[reportDeprecated],
            )
        )
        self.stats = async_to_streamed_response_wrapper(
            runs.stats,
        )
        self.update_2 = async_to_streamed_response_wrapper(
            runs.update_2,
        )

    @cached_property
    def share(self) -> AsyncShareResourceWithStreamingResponse:
        return AsyncShareResourceWithStreamingResponse(self._runs.share)
