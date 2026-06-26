# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform
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
from ...types.datasets import experiment_run_create_params
from ...types.datasets.experiment_run_create_response import ExperimentRunCreateResponse

__all__ = ["ExperimentRunsResource", "AsyncExperimentRunsResource"]


class ExperimentRunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ExperimentRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return ExperimentRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExperimentRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return ExperimentRunsResourceWithStreamingResponse(self)

    def create(
        self,
        dataset_id: str,
        *,
        comparative_experiment_id: str | Omit = omit,
        cursor: str | Omit = omit,
        example_ids: SequenceNotStr[str] | Omit = omit,
        experiment_ids: SequenceNotStr[str] | Omit = omit,
        filters: Dict[str, SequenceNotStr[str]] | Omit = omit,
        page_size: int | Omit = omit,
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
        sort: experiment_run_create_params.Sort | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorPostPagination[ExperimentRunCreateResponse]:
        """
        Returns a paginated page of dataset examples with runs from the requested
        experiments. Response uses the canonical `{items, next_cursor}` envelope.

        Args:
          comparative_experiment_id: `comparative_experiment_id` scopes pairwise-annotation feedback (optional).

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Absent
              for the first page.

          example_ids: `example_ids` optionally restricts the page to these dataset example UUIDs (max
              1000).

          experiment_ids: `experiment_ids` lists the experiment (tracing session) UUIDs to query.
              Required, non-empty.

          filters: `filters` maps a project (session) UUID string to a list of filter expressions
              (optional).

          page_size: `page_size` is the maximum number of examples to return. Defaults to 20,
              max 100.

          selects: `selects` lists which run properties to include. Omitted => only `id`. Tokens
              mirror /v2/runs/query.

          sort: `sort` controls feedback-score sorting (single project only).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get_api_list(
            path_template("/v2/datasets/{dataset_id}/experiment-runs", dataset_id=dataset_id),
            page=SyncItemsCursorPostPagination[ExperimentRunCreateResponse],
            body=maybe_transform(
                {
                    "comparative_experiment_id": comparative_experiment_id,
                    "cursor": cursor,
                    "example_ids": example_ids,
                    "experiment_ids": experiment_ids,
                    "filters": filters,
                    "page_size": page_size,
                    "selects": selects,
                    "sort": sort,
                },
                experiment_run_create_params.ExperimentRunCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ExperimentRunCreateResponse,
            method="post",
        )


class AsyncExperimentRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncExperimentRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return AsyncExperimentRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExperimentRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return AsyncExperimentRunsResourceWithStreamingResponse(self)

    def create(
        self,
        dataset_id: str,
        *,
        comparative_experiment_id: str | Omit = omit,
        cursor: str | Omit = omit,
        example_ids: SequenceNotStr[str] | Omit = omit,
        experiment_ids: SequenceNotStr[str] | Omit = omit,
        filters: Dict[str, SequenceNotStr[str]] | Omit = omit,
        page_size: int | Omit = omit,
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
        sort: experiment_run_create_params.Sort | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[ExperimentRunCreateResponse, AsyncItemsCursorPostPagination[ExperimentRunCreateResponse]]:
        """
        Returns a paginated page of dataset examples with runs from the requested
        experiments. Response uses the canonical `{items, next_cursor}` envelope.

        Args:
          comparative_experiment_id: `comparative_experiment_id` scopes pairwise-annotation feedback (optional).

          cursor: `cursor` is the opaque string from a previous response's `next_cursor`. Absent
              for the first page.

          example_ids: `example_ids` optionally restricts the page to these dataset example UUIDs (max
              1000).

          experiment_ids: `experiment_ids` lists the experiment (tracing session) UUIDs to query.
              Required, non-empty.

          filters: `filters` maps a project (session) UUID string to a list of filter expressions
              (optional).

          page_size: `page_size` is the maximum number of examples to return. Defaults to 20,
              max 100.

          selects: `selects` lists which run properties to include. Omitted => only `id`. Tokens
              mirror /v2/runs/query.

          sort: `sort` controls feedback-score sorting (single project only).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get_api_list(
            path_template("/v2/datasets/{dataset_id}/experiment-runs", dataset_id=dataset_id),
            page=AsyncItemsCursorPostPagination[ExperimentRunCreateResponse],
            body=maybe_transform(
                {
                    "comparative_experiment_id": comparative_experiment_id,
                    "cursor": cursor,
                    "example_ids": example_ids,
                    "experiment_ids": experiment_ids,
                    "filters": filters,
                    "page_size": page_size,
                    "selects": selects,
                    "sort": sort,
                },
                experiment_run_create_params.ExperimentRunCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ExperimentRunCreateResponse,
            method="post",
        )


class ExperimentRunsResourceWithRawResponse:
    def __init__(self, experiment_runs: ExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.create = to_raw_response_wrapper(
            experiment_runs.create,
        )


class AsyncExperimentRunsResourceWithRawResponse:
    def __init__(self, experiment_runs: AsyncExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.create = async_to_raw_response_wrapper(
            experiment_runs.create,
        )


class ExperimentRunsResourceWithStreamingResponse:
    def __init__(self, experiment_runs: ExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.create = to_streamed_response_wrapper(
            experiment_runs.create,
        )


class AsyncExperimentRunsResourceWithStreamingResponse:
    def __init__(self, experiment_runs: AsyncExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.create = async_to_streamed_response_wrapper(
            experiment_runs.create,
        )
