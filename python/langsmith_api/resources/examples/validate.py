# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..._types import Body, Query, Headers, NotGiven, not_given
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.examples.validate_bulk_response import ValidateBulkResponse
from ...types.examples.example_validation_result import ExampleValidationResult

__all__ = ["ValidateResource", "AsyncValidateResource"]


class ValidateResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ValidateResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ValidateResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ValidateResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ValidateResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleValidationResult:
        """Validate an example."""
        return self._post(
            "/api/v1/examples/validate",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ExampleValidationResult,
        )

    def bulk(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ValidateBulkResponse:
        """Validate examples in bulk."""
        return self._post(
            "/api/v1/examples/validate/bulk",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ValidateBulkResponse,
        )


class AsyncValidateResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncValidateResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncValidateResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncValidateResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncValidateResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleValidationResult:
        """Validate an example."""
        return await self._post(
            "/api/v1/examples/validate",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ExampleValidationResult,
        )

    async def bulk(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ValidateBulkResponse:
        """Validate examples in bulk."""
        return await self._post(
            "/api/v1/examples/validate/bulk",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ValidateBulkResponse,
        )


class ValidateResourceWithRawResponse:
    def __init__(self, validate: ValidateResource) -> None:
        self._validate = validate

        self.create = to_raw_response_wrapper(
            validate.create,
        )
        self.bulk = to_raw_response_wrapper(
            validate.bulk,
        )


class AsyncValidateResourceWithRawResponse:
    def __init__(self, validate: AsyncValidateResource) -> None:
        self._validate = validate

        self.create = async_to_raw_response_wrapper(
            validate.create,
        )
        self.bulk = async_to_raw_response_wrapper(
            validate.bulk,
        )


class ValidateResourceWithStreamingResponse:
    def __init__(self, validate: ValidateResource) -> None:
        self._validate = validate

        self.create = to_streamed_response_wrapper(
            validate.create,
        )
        self.bulk = to_streamed_response_wrapper(
            validate.bulk,
        )


class AsyncValidateResourceWithStreamingResponse:
    def __init__(self, validate: AsyncValidateResource) -> None:
        self._validate = validate

        self.create = async_to_streamed_response_wrapper(
            validate.create,
        )
        self.bulk = async_to_streamed_response_wrapper(
            validate.bulk,
        )
