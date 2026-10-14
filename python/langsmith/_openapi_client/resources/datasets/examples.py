# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from ..._httpx import httpx
from ..._types import Body, Query, Headers, NoneType, NotGiven, not_given
from ..._utils import path_template
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options

__all__ = ["ExamplesResource", "AsyncExamplesResource"]


class ExamplesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return ExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return ExamplesResourceWithStreamingResponse(self)

    def delete(
        self,
        example_id: str,
        *,
        dataset_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Soft-delete an example, preserving prior versions and their attachments.

        If the
        latest version is already deleted, the request succeeds without creating another
        version. Deletion is recorded at the current time or just after the latest
        version, whichever is later. For future-dated versions, latest reads reflect
        deletion immediately; timestamp reads reflect deletion only at or after the
        recorded deletion timestamp.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template(
                "/api/v1/platform/datasets/{dataset_id}/examples/{example_id}",
                dataset_id=dataset_id,
                example_id=example_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class AsyncExamplesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return AsyncExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return AsyncExamplesResourceWithStreamingResponse(self)

    async def delete(
        self,
        example_id: str,
        *,
        dataset_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Soft-delete an example, preserving prior versions and their attachments.

        If the
        latest version is already deleted, the request succeeds without creating another
        version. Deletion is recorded at the current time or just after the latest
        version, whichever is later. For future-dated versions, latest reads reflect
        deletion immediately; timestamp reads reflect deletion only at or after the
        recorded deletion timestamp.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template(
                "/api/v1/platform/datasets/{dataset_id}/examples/{example_id}",
                dataset_id=dataset_id,
                example_id=example_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class ExamplesResourceWithRawResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.delete = to_raw_response_wrapper(
            examples.delete,
        )


class AsyncExamplesResourceWithRawResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.delete = async_to_raw_response_wrapper(
            examples.delete,
        )


class ExamplesResourceWithStreamingResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.delete = to_streamed_response_wrapper(
            examples.delete,
        )


class AsyncExamplesResourceWithStreamingResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.delete = async_to_streamed_response_wrapper(
            examples.delete,
        )
