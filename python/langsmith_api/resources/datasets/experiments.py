# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime

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
from ...types.datasets import experiment_grouped_params

__all__ = ["ExperimentsResource", "AsyncExperimentsResource"]


class ExperimentsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ExperimentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ExperimentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExperimentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ExperimentsResourceWithStreamingResponse(self)

    def grouped(
        self,
        dataset_id: str,
        *,
        metadata_keys: SequenceNotStr[str],
        dataset_version: Optional[str] | Omit = omit,
        experiment_limit: int | Omit = omit,
        filter: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        use_approx_stats: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Stream grouped and aggregated experiments.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._post(
            path_template("/api/v1/datasets/{dataset_id}/experiments/grouped", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "metadata_keys": metadata_keys,
                    "dataset_version": dataset_version,
                    "experiment_limit": experiment_limit,
                    "filter": filter,
                    "name_contains": name_contains,
                    "stats_start_time": stats_start_time,
                    "tag_value_id": tag_value_id,
                    "use_approx_stats": use_approx_stats,
                },
                experiment_grouped_params.ExperimentGroupedParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncExperimentsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncExperimentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncExperimentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExperimentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncExperimentsResourceWithStreamingResponse(self)

    async def grouped(
        self,
        dataset_id: str,
        *,
        metadata_keys: SequenceNotStr[str],
        dataset_version: Optional[str] | Omit = omit,
        experiment_limit: int | Omit = omit,
        filter: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        use_approx_stats: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Stream grouped and aggregated experiments.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._post(
            path_template("/api/v1/datasets/{dataset_id}/experiments/grouped", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "metadata_keys": metadata_keys,
                    "dataset_version": dataset_version,
                    "experiment_limit": experiment_limit,
                    "filter": filter,
                    "name_contains": name_contains,
                    "stats_start_time": stats_start_time,
                    "tag_value_id": tag_value_id,
                    "use_approx_stats": use_approx_stats,
                },
                experiment_grouped_params.ExperimentGroupedParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class ExperimentsResourceWithRawResponse:
    def __init__(self, experiments: ExperimentsResource) -> None:
        self._experiments = experiments

        self.grouped = to_raw_response_wrapper(
            experiments.grouped,
        )


class AsyncExperimentsResourceWithRawResponse:
    def __init__(self, experiments: AsyncExperimentsResource) -> None:
        self._experiments = experiments

        self.grouped = async_to_raw_response_wrapper(
            experiments.grouped,
        )


class ExperimentsResourceWithStreamingResponse:
    def __init__(self, experiments: ExperimentsResource) -> None:
        self._experiments = experiments

        self.grouped = to_streamed_response_wrapper(
            experiments.grouped,
        )


class AsyncExperimentsResourceWithStreamingResponse:
    def __init__(self, experiments: AsyncExperimentsResource) -> None:
        self._experiments = experiments

        self.grouped = async_to_streamed_response_wrapper(
            experiments.grouped,
        )
