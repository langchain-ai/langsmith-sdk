# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal

from ..types import product_feedback_create_params
from .._httpx import httpx
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options
from ..types.product_feedback_create_response import ProductFeedbackCreateResponse
from ..types.product_feedback_retrieve_response import ProductFeedbackRetrieveResponse

__all__ = ["ProductFeedbackResource", "AsyncProductFeedbackResource"]


class ProductFeedbackResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ProductFeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return ProductFeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ProductFeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return ProductFeedbackResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        category: Literal["BUG", "FEATURE_REQUEST", "USABILITY", "DOCUMENTATION", "OTHER"],
        message: str,
        source: Literal["LANGSMITH_CLI"],
        client: product_feedback_create_params.Client | Omit = omit,
        idempotency_key: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProductFeedbackCreateResponse:
        """
        **Alpha:** This endpoint is in active development and may change without notice.

        Submits concise product feedback with optional non-sensitive client details.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"Idempotency-Key": idempotency_key}), **(extra_headers or {})}
        return self._post(
            "/api/v1/platform/product-feedbacks",
            body=maybe_transform(
                {
                    "category": category,
                    "message": message,
                    "source": source,
                    "client": client,
                },
                product_feedback_create_params.ProductFeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProductFeedbackCreateResponse,
        )

    def retrieve(
        self,
        id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProductFeedbackRetrieveResponse:
        """
        **Alpha:** This endpoint is in active development and may change without notice.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not id:
            raise ValueError(f"Expected a non-empty value for `id` but received {id!r}")
        return self._get(
            path_template("/api/v1/platform/product-feedbacks/{id}", id=id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProductFeedbackRetrieveResponse,
        )


class AsyncProductFeedbackResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncProductFeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncProductFeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncProductFeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncProductFeedbackResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        category: Literal["BUG", "FEATURE_REQUEST", "USABILITY", "DOCUMENTATION", "OTHER"],
        message: str,
        source: Literal["LANGSMITH_CLI"],
        client: product_feedback_create_params.Client | Omit = omit,
        idempotency_key: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProductFeedbackCreateResponse:
        """
        **Alpha:** This endpoint is in active development and may change without notice.

        Submits concise product feedback with optional non-sensitive client details.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"Idempotency-Key": idempotency_key}), **(extra_headers or {})}
        return await self._post(
            "/api/v1/platform/product-feedbacks",
            body=await async_maybe_transform(
                {
                    "category": category,
                    "message": message,
                    "source": source,
                    "client": client,
                },
                product_feedback_create_params.ProductFeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProductFeedbackCreateResponse,
        )

    async def retrieve(
        self,
        id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProductFeedbackRetrieveResponse:
        """
        **Alpha:** This endpoint is in active development and may change without notice.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not id:
            raise ValueError(f"Expected a non-empty value for `id` but received {id!r}")
        return await self._get(
            path_template("/api/v1/platform/product-feedbacks/{id}", id=id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProductFeedbackRetrieveResponse,
        )


class ProductFeedbackResourceWithRawResponse:
    def __init__(self, product_feedback: ProductFeedbackResource) -> None:
        self._product_feedback = product_feedback

        self.create = to_raw_response_wrapper(
            product_feedback.create,
        )
        self.retrieve = to_raw_response_wrapper(
            product_feedback.retrieve,
        )


class AsyncProductFeedbackResourceWithRawResponse:
    def __init__(self, product_feedback: AsyncProductFeedbackResource) -> None:
        self._product_feedback = product_feedback

        self.create = async_to_raw_response_wrapper(
            product_feedback.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            product_feedback.retrieve,
        )


class ProductFeedbackResourceWithStreamingResponse:
    def __init__(self, product_feedback: ProductFeedbackResource) -> None:
        self._product_feedback = product_feedback

        self.create = to_streamed_response_wrapper(
            product_feedback.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            product_feedback.retrieve,
        )


class AsyncProductFeedbackResourceWithStreamingResponse:
    def __init__(self, product_feedback: AsyncProductFeedbackResource) -> None:
        self._product_feedback = product_feedback

        self.create = async_to_streamed_response_wrapper(
            product_feedback.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            product_feedback.retrieve,
        )
