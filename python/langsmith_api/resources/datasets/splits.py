# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
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
from ...types.datasets import split_create_params, split_retrieve_params
from ...types.datasets.split_create_response import SplitCreateResponse
from ...types.datasets.split_retrieve_response import SplitRetrieveResponse

__all__ = ["SplitsResource", "AsyncSplitsResource"]


class SplitsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SplitsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return SplitsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SplitsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return SplitsResourceWithStreamingResponse(self)

    def create(
        self,
        dataset_id: str,
        *,
        examples: SequenceNotStr[str],
        split_name: str,
        remove: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SplitCreateResponse:
        """
        Update Dataset Splits

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._put(
            path_template("/api/v1/datasets/{dataset_id}/splits", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "examples": examples,
                    "split_name": split_name,
                    "remove": remove,
                },
                split_create_params.SplitCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SplitCreateResponse,
        )

    def retrieve(
        self,
        dataset_id: str,
        *,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SplitRetrieveResponse:
        """
        Get Dataset Splits

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/splits", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"as_of": as_of}, split_retrieve_params.SplitRetrieveParams),
            ),
            cast_to=SplitRetrieveResponse,
        )


class AsyncSplitsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSplitsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSplitsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSplitsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncSplitsResourceWithStreamingResponse(self)

    async def create(
        self,
        dataset_id: str,
        *,
        examples: SequenceNotStr[str],
        split_name: str,
        remove: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SplitCreateResponse:
        """
        Update Dataset Splits

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._put(
            path_template("/api/v1/datasets/{dataset_id}/splits", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "examples": examples,
                    "split_name": split_name,
                    "remove": remove,
                },
                split_create_params.SplitCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SplitCreateResponse,
        )

    async def retrieve(
        self,
        dataset_id: str,
        *,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SplitRetrieveResponse:
        """
        Get Dataset Splits

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/splits", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"as_of": as_of}, split_retrieve_params.SplitRetrieveParams),
            ),
            cast_to=SplitRetrieveResponse,
        )


class SplitsResourceWithRawResponse:
    def __init__(self, splits: SplitsResource) -> None:
        self._splits = splits

        self.create = to_raw_response_wrapper(
            splits.create,
        )
        self.retrieve = to_raw_response_wrapper(
            splits.retrieve,
        )


class AsyncSplitsResourceWithRawResponse:
    def __init__(self, splits: AsyncSplitsResource) -> None:
        self._splits = splits

        self.create = async_to_raw_response_wrapper(
            splits.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            splits.retrieve,
        )


class SplitsResourceWithStreamingResponse:
    def __init__(self, splits: SplitsResource) -> None:
        self._splits = splits

        self.create = to_streamed_response_wrapper(
            splits.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            splits.retrieve,
        )


class AsyncSplitsResourceWithStreamingResponse:
    def __init__(self, splits: AsyncSplitsResource) -> None:
        self._splits = splits

        self.create = async_to_streamed_response_wrapper(
            splits.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            splits.retrieve,
        )
