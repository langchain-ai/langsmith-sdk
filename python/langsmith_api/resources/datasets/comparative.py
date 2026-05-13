# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
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
from ...types.datasets import comparative_create_params
from ...types.datasets.comparative_create_response import ComparativeCreateResponse

__all__ = ["ComparativeResource", "AsyncComparativeResource"]


class ComparativeResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ComparativeResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ComparativeResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ComparativeResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ComparativeResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        experiment_ids: SequenceNotStr[str],
        id: str | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        description: Optional[str] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        modified_at: Union[str, datetime] | Omit = omit,
        name: Optional[str] | Omit = omit,
        reference_dataset_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ComparativeCreateResponse:
        """
        Create a comparative experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/datasets/comparative",
            body=maybe_transform(
                {
                    "experiment_ids": experiment_ids,
                    "id": id,
                    "created_at": created_at,
                    "description": description,
                    "extra": extra,
                    "modified_at": modified_at,
                    "name": name,
                    "reference_dataset_id": reference_dataset_id,
                },
                comparative_create_params.ComparativeCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ComparativeCreateResponse,
        )

    def delete(
        self,
        comparative_experiment_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific comparative experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not comparative_experiment_id:
            raise ValueError(
                f"Expected a non-empty value for `comparative_experiment_id` but received {comparative_experiment_id!r}"
            )
        return self._delete(
            path_template(
                "/api/v1/datasets/comparative/{comparative_experiment_id}",
                comparative_experiment_id=comparative_experiment_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncComparativeResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncComparativeResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncComparativeResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncComparativeResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncComparativeResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        experiment_ids: SequenceNotStr[str],
        id: str | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        description: Optional[str] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        modified_at: Union[str, datetime] | Omit = omit,
        name: Optional[str] | Omit = omit,
        reference_dataset_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ComparativeCreateResponse:
        """
        Create a comparative experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/datasets/comparative",
            body=await async_maybe_transform(
                {
                    "experiment_ids": experiment_ids,
                    "id": id,
                    "created_at": created_at,
                    "description": description,
                    "extra": extra,
                    "modified_at": modified_at,
                    "name": name,
                    "reference_dataset_id": reference_dataset_id,
                },
                comparative_create_params.ComparativeCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ComparativeCreateResponse,
        )

    async def delete(
        self,
        comparative_experiment_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific comparative experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not comparative_experiment_id:
            raise ValueError(
                f"Expected a non-empty value for `comparative_experiment_id` but received {comparative_experiment_id!r}"
            )
        return await self._delete(
            path_template(
                "/api/v1/datasets/comparative/{comparative_experiment_id}",
                comparative_experiment_id=comparative_experiment_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class ComparativeResourceWithRawResponse:
    def __init__(self, comparative: ComparativeResource) -> None:
        self._comparative = comparative

        self.create = to_raw_response_wrapper(
            comparative.create,
        )
        self.delete = to_raw_response_wrapper(
            comparative.delete,
        )


class AsyncComparativeResourceWithRawResponse:
    def __init__(self, comparative: AsyncComparativeResource) -> None:
        self._comparative = comparative

        self.create = async_to_raw_response_wrapper(
            comparative.create,
        )
        self.delete = async_to_raw_response_wrapper(
            comparative.delete,
        )


class ComparativeResourceWithStreamingResponse:
    def __init__(self, comparative: ComparativeResource) -> None:
        self._comparative = comparative

        self.create = to_streamed_response_wrapper(
            comparative.create,
        )
        self.delete = to_streamed_response_wrapper(
            comparative.delete,
        )


class AsyncComparativeResourceWithStreamingResponse:
    def __init__(self, comparative: AsyncComparativeResource) -> None:
        self._comparative = comparative

        self.create = async_to_streamed_response_wrapper(
            comparative.create,
        )
        self.delete = async_to_streamed_response_wrapper(
            comparative.delete,
        )
