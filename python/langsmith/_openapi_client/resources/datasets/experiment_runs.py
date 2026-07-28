# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List

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
from ...types.datasets import experiment_run_query_params
from ...types.run_select_field import RunSelectField
from ...types.datasets.experiment_run_query_response import ExperimentRunQueryResponse

__all__ = ["ExperimentRunsResource", "AsyncExperimentRunsResource"]


class ExperimentRunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ExperimentRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return ExperimentRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExperimentRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return ExperimentRunsResourceWithStreamingResponse(self)

    def query(
        self,
        dataset_id: str,
        *,
        comparative_experiment_id: str | Omit = omit,
        cursor: str | Omit = omit,
        example_ids: SequenceNotStr[str] | Omit = omit,
        experiment_ids: SequenceNotStr[str] | Omit = omit,
        filters: Dict[str, SequenceNotStr[str]] | Omit = omit,
        page_size: int | Omit = omit,
        selects: List[RunSelectField] | Omit = omit,
        sort: experiment_run_query_params.Sort | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorPostPagination[ExperimentRunQueryResponse]:
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
            page=SyncItemsCursorPostPagination[ExperimentRunQueryResponse],
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
                experiment_run_query_params.ExperimentRunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ExperimentRunQueryResponse,
            method="post",
        )


class AsyncExperimentRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncExperimentRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncExperimentRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExperimentRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncExperimentRunsResourceWithStreamingResponse(self)

    def query(
        self,
        dataset_id: str,
        *,
        comparative_experiment_id: str | Omit = omit,
        cursor: str | Omit = omit,
        example_ids: SequenceNotStr[str] | Omit = omit,
        experiment_ids: SequenceNotStr[str] | Omit = omit,
        filters: Dict[str, SequenceNotStr[str]] | Omit = omit,
        page_size: int | Omit = omit,
        selects: List[RunSelectField] | Omit = omit,
        sort: experiment_run_query_params.Sort | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[ExperimentRunQueryResponse, AsyncItemsCursorPostPagination[ExperimentRunQueryResponse]]:
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
            page=AsyncItemsCursorPostPagination[ExperimentRunQueryResponse],
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
                experiment_run_query_params.ExperimentRunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            model=ExperimentRunQueryResponse,
            method="post",
        )


class ExperimentRunsResourceWithRawResponse:
    def __init__(self, experiment_runs: ExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.query = to_raw_response_wrapper(
            experiment_runs.query,
        )


class AsyncExperimentRunsResourceWithRawResponse:
    def __init__(self, experiment_runs: AsyncExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.query = async_to_raw_response_wrapper(
            experiment_runs.query,
        )


class ExperimentRunsResourceWithStreamingResponse:
    def __init__(self, experiment_runs: ExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.query = to_streamed_response_wrapper(
            experiment_runs.query,
        )


class AsyncExperimentRunsResourceWithStreamingResponse:
    def __init__(self, experiment_runs: AsyncExperimentRunsResource) -> None:
        self._experiment_runs = experiment_runs

        self.query = async_to_streamed_response_wrapper(
            experiment_runs.query,
        )
