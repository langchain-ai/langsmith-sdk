# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.datasets import run_query_params
from ...types.datasets.run_query_response import RunQueryResponse
from ...types.datasets.sort_params_for_runs_comparison_view_param import SortParamsForRunsComparisonViewParam

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

    def query(
        self,
        dataset_id: str,
        *,
        session_ids: SequenceNotStr[str],
        format: Optional[Literal["csv"]] | Omit = omit,
        comparative_experiment_id: Optional[str] | Omit = omit,
        example_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        filters: Optional[Dict[str, SequenceNotStr[str]]] | Omit = omit,
        include_annotator_detail: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: int | Omit = omit,
        preview: bool | Omit = omit,
        sort_params: Optional[SortParamsForRunsComparisonViewParam] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Optional[RunQueryResponse]:
        """
        Fetch examples for a dataset, and fetch the runs for each example if they are
        associated with the given session_ids.

        Args:
          format: Response format, e.g., 'csv'

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._post(
            path_template("/api/v1/datasets/{dataset_id}/runs", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "session_ids": session_ids,
                    "comparative_experiment_id": comparative_experiment_id,
                    "example_ids": example_ids,
                    "filters": filters,
                    "include_annotator_detail": include_annotator_detail,
                    "limit": limit,
                    "offset": offset,
                    "preview": preview,
                    "sort_params": sort_params,
                },
                run_query_params.RunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"format": format}, run_query_params.RunQueryParams),
            ),
            cast_to=RunQueryResponse,
        )


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

    async def query(
        self,
        dataset_id: str,
        *,
        session_ids: SequenceNotStr[str],
        format: Optional[Literal["csv"]] | Omit = omit,
        comparative_experiment_id: Optional[str] | Omit = omit,
        example_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        filters: Optional[Dict[str, SequenceNotStr[str]]] | Omit = omit,
        include_annotator_detail: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: int | Omit = omit,
        preview: bool | Omit = omit,
        sort_params: Optional[SortParamsForRunsComparisonViewParam] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Optional[RunQueryResponse]:
        """
        Fetch examples for a dataset, and fetch the runs for each example if they are
        associated with the given session_ids.

        Args:
          format: Response format, e.g., 'csv'

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._post(
            path_template("/api/v1/datasets/{dataset_id}/runs", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "session_ids": session_ids,
                    "comparative_experiment_id": comparative_experiment_id,
                    "example_ids": example_ids,
                    "filters": filters,
                    "include_annotator_detail": include_annotator_detail,
                    "limit": limit,
                    "offset": offset,
                    "preview": preview,
                    "sort_params": sort_params,
                },
                run_query_params.RunQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"format": format}, run_query_params.RunQueryParams),
            ),
            cast_to=RunQueryResponse,
        )


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.query = to_raw_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.query = async_to_raw_response_wrapper(
            runs.query,
        )


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.query = to_streamed_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.query = async_to_streamed_response_wrapper(
            runs.query,
        )
