# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from datetime import datetime

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
from ...pagination import SyncOffsetPaginationTopLevelArray, AsyncOffsetPaginationTopLevelArray
from ..._base_client import AsyncPaginator, make_request_options
from ...types.public import example_list_params
from ...types.example import Example
from ...types.example_select import ExampleSelect

__all__ = ["ExamplesResource", "AsyncExamplesResource"]


class ExamplesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ExamplesResourceWithStreamingResponse(self)

    def list(
        self,
        share_token: str,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        select: List[ExampleSelect] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[Example]:
        """
        Get example by ids or the shared example if not specifed.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/examples", share_token=share_token),
            page=SyncOffsetPaginationTopLevelArray[Example],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "filter": filter,
                        "limit": limit,
                        "metadata": metadata,
                        "offset": offset,
                        "select": select,
                    },
                    example_list_params.ExampleListParams,
                ),
            ),
            model=Example,
        )


class AsyncExamplesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncExamplesResourceWithStreamingResponse(self)

    def list(
        self,
        share_token: str,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        select: List[ExampleSelect] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[Example, AsyncOffsetPaginationTopLevelArray[Example]]:
        """
        Get example by ids or the shared example if not specifed.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/examples", share_token=share_token),
            page=AsyncOffsetPaginationTopLevelArray[Example],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "filter": filter,
                        "limit": limit,
                        "metadata": metadata,
                        "offset": offset,
                        "select": select,
                    },
                    example_list_params.ExampleListParams,
                ),
            ),
            model=Example,
        )


class ExamplesResourceWithRawResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.list = to_raw_response_wrapper(
            examples.list,
        )


class AsyncExamplesResourceWithRawResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.list = async_to_raw_response_wrapper(
            examples.list,
        )


class ExamplesResourceWithStreamingResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.list = to_streamed_response_wrapper(
            examples.list,
        )


class AsyncExamplesResourceWithStreamingResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.list = async_to_streamed_response_wrapper(
            examples.list,
        )
