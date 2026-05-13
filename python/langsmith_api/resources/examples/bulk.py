# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable

import httpx

from ..._types import Body, Query, Headers, NotGiven, SequenceNotStr, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.examples import bulk_create_params, bulk_delete_params, bulk_patch_all_params
from ...types.examples.bulk_create_response import BulkCreateResponse
from ...types.examples.bulk_delete_response import BulkDeleteResponse

__all__ = ["BulkResource", "AsyncBulkResource"]


class BulkResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> BulkResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return BulkResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> BulkResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return BulkResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        body: Iterable[bulk_create_params.Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkCreateResponse:
        """
        Create bulk examples.

        Args:
          body: Schema for a batch of examples to be created.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/examples/bulk",
            body=maybe_transform(body, Iterable[bulk_create_params.Body]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=BulkCreateResponse,
        )

    def delete(
        self,
        *,
        example_ids: SequenceNotStr[str],
        hard_delete: bool,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkDeleteResponse:
        """This endpoint hard deletes _all_ versions of a dataset example(s).

        Deletion is
        performed by setting inputs, outputs, and metadata to null and deleting
        attachment files while keeping the example ID, dataset ID, and creation
        timestamp. IMPORTANT: attachment files can take up to 7 days to be deleted.
        inputs, outputs and metadata are nullified immediately.

        Args:
          example_ids: ExampleIDs is a list of UUIDs identifying the examples to delete.

          hard_delete: HardDelete indicates whether to perform a hard delete. Currently only True is
              supported.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/v1/platform/datasets/examples/delete",
            body=maybe_transform(
                {
                    "example_ids": example_ids,
                    "hard_delete": hard_delete,
                },
                bulk_delete_params.BulkDeleteParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=BulkDeleteResponse,
        )

    def patch_all(
        self,
        *,
        body: Iterable[bulk_patch_all_params.Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Legacy update examples in bulk.

        For update involving attachments, use PATCH
        /v1/platform/datasets/{dataset_id}/examples instead.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._patch(
            "/api/v1/examples/bulk",
            body=maybe_transform(body, Iterable[bulk_patch_all_params.Body]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncBulkResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncBulkResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncBulkResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncBulkResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncBulkResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        body: Iterable[bulk_create_params.Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkCreateResponse:
        """
        Create bulk examples.

        Args:
          body: Schema for a batch of examples to be created.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/examples/bulk",
            body=await async_maybe_transform(body, Iterable[bulk_create_params.Body]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=BulkCreateResponse,
        )

    async def delete(
        self,
        *,
        example_ids: SequenceNotStr[str],
        hard_delete: bool,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkDeleteResponse:
        """This endpoint hard deletes _all_ versions of a dataset example(s).

        Deletion is
        performed by setting inputs, outputs, and metadata to null and deleting
        attachment files while keeping the example ID, dataset ID, and creation
        timestamp. IMPORTANT: attachment files can take up to 7 days to be deleted.
        inputs, outputs and metadata are nullified immediately.

        Args:
          example_ids: ExampleIDs is a list of UUIDs identifying the examples to delete.

          hard_delete: HardDelete indicates whether to perform a hard delete. Currently only True is
              supported.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/v1/platform/datasets/examples/delete",
            body=await async_maybe_transform(
                {
                    "example_ids": example_ids,
                    "hard_delete": hard_delete,
                },
                bulk_delete_params.BulkDeleteParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=BulkDeleteResponse,
        )

    async def patch_all(
        self,
        *,
        body: Iterable[bulk_patch_all_params.Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Legacy update examples in bulk.

        For update involving attachments, use PATCH
        /v1/platform/datasets/{dataset_id}/examples instead.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._patch(
            "/api/v1/examples/bulk",
            body=await async_maybe_transform(body, Iterable[bulk_patch_all_params.Body]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class BulkResourceWithRawResponse:
    def __init__(self, bulk: BulkResource) -> None:
        self._bulk = bulk

        self.create = to_raw_response_wrapper(
            bulk.create,
        )
        self.delete = to_raw_response_wrapper(
            bulk.delete,
        )
        self.patch_all = to_raw_response_wrapper(
            bulk.patch_all,
        )


class AsyncBulkResourceWithRawResponse:
    def __init__(self, bulk: AsyncBulkResource) -> None:
        self._bulk = bulk

        self.create = async_to_raw_response_wrapper(
            bulk.create,
        )
        self.delete = async_to_raw_response_wrapper(
            bulk.delete,
        )
        self.patch_all = async_to_raw_response_wrapper(
            bulk.patch_all,
        )


class BulkResourceWithStreamingResponse:
    def __init__(self, bulk: BulkResource) -> None:
        self._bulk = bulk

        self.create = to_streamed_response_wrapper(
            bulk.create,
        )
        self.delete = to_streamed_response_wrapper(
            bulk.delete,
        )
        self.patch_all = to_streamed_response_wrapper(
            bulk.patch_all,
        )


class AsyncBulkResourceWithStreamingResponse:
    def __init__(self, bulk: AsyncBulkResource) -> None:
        self._bulk = bulk

        self.create = async_to_streamed_response_wrapper(
            bulk.create,
        )
        self.delete = async_to_streamed_response_wrapper(
            bulk.delete,
        )
        self.patch_all = async_to_streamed_response_wrapper(
            bulk.patch_all,
        )
