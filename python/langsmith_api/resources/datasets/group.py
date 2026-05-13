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
from ...types.datasets import group_runs_params
from ...types.datasets.group_runs_response import GroupRunsResponse

__all__ = ["GroupResource", "AsyncGroupResource"]


class GroupResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> GroupResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return GroupResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> GroupResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return GroupResourceWithStreamingResponse(self)

    def runs(
        self,
        dataset_id: str,
        *,
        group_by: Literal["run_metadata", "example_metadata"],
        metadata_key: str,
        session_ids: SequenceNotStr[str],
        filters: Optional[Dict[str, SequenceNotStr[str]]] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        per_group_limit: int | Omit = omit,
        preview: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GroupRunsResponse:
        """
        Fetch examples for a dataset, and fetch the runs for each example if they are
        associated with the given session_ids.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._post(
            path_template("/api/v1/datasets/{dataset_id}/group/runs", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "group_by": group_by,
                    "metadata_key": metadata_key,
                    "session_ids": session_ids,
                    "filters": filters,
                    "limit": limit,
                    "offset": offset,
                    "per_group_limit": per_group_limit,
                    "preview": preview,
                },
                group_runs_params.GroupRunsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=GroupRunsResponse,
        )


class AsyncGroupResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncGroupResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncGroupResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncGroupResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncGroupResourceWithStreamingResponse(self)

    async def runs(
        self,
        dataset_id: str,
        *,
        group_by: Literal["run_metadata", "example_metadata"],
        metadata_key: str,
        session_ids: SequenceNotStr[str],
        filters: Optional[Dict[str, SequenceNotStr[str]]] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        per_group_limit: int | Omit = omit,
        preview: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GroupRunsResponse:
        """
        Fetch examples for a dataset, and fetch the runs for each example if they are
        associated with the given session_ids.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._post(
            path_template("/api/v1/datasets/{dataset_id}/group/runs", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "group_by": group_by,
                    "metadata_key": metadata_key,
                    "session_ids": session_ids,
                    "filters": filters,
                    "limit": limit,
                    "offset": offset,
                    "per_group_limit": per_group_limit,
                    "preview": preview,
                },
                group_runs_params.GroupRunsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=GroupRunsResponse,
        )


class GroupResourceWithRawResponse:
    def __init__(self, group: GroupResource) -> None:
        self._group = group

        self.runs = to_raw_response_wrapper(
            group.runs,
        )


class AsyncGroupResourceWithRawResponse:
    def __init__(self, group: AsyncGroupResource) -> None:
        self._group = group

        self.runs = async_to_raw_response_wrapper(
            group.runs,
        )


class GroupResourceWithStreamingResponse:
    def __init__(self, group: GroupResource) -> None:
        self._group = group

        self.runs = to_streamed_response_wrapper(
            group.runs,
        )


class AsyncGroupResourceWithStreamingResponse:
    def __init__(self, group: AsyncGroupResource) -> None:
        self._group = group

        self.runs = async_to_streamed_response_wrapper(
            group.runs,
        )
