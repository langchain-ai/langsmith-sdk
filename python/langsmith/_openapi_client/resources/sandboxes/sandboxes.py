# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Literal

from .boxes import (
    BoxesResource,
    AsyncBoxesResource,
    BoxesResourceWithRawResponse,
    AsyncBoxesResourceWithRawResponse,
    BoxesResourceWithStreamingResponse,
    AsyncBoxesResourceWithStreamingResponse,
)
from ...types import sandbox_list_usage_costs_params
from ..._httpx import httpx
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import maybe_transform
from ..._compat import cached_property
from .snapshots import (
    SnapshotsResource,
    AsyncSnapshotsResource,
    SnapshotsResourceWithRawResponse,
    AsyncSnapshotsResourceWithRawResponse,
    SnapshotsResourceWithStreamingResponse,
    AsyncSnapshotsResourceWithStreamingResponse,
)
from .registries import (
    RegistriesResource,
    AsyncRegistriesResource,
    RegistriesResourceWithRawResponse,
    AsyncRegistriesResourceWithRawResponse,
    RegistriesResourceWithStreamingResponse,
    AsyncRegistriesResourceWithStreamingResponse,
)
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import SyncItemsCursorGetPagination, AsyncItemsCursorGetPagination
from ..._base_client import AsyncPaginator, make_request_options
from ...types.sandbox_list_usage_costs_response import SandboxListUsageCostsResponse

__all__ = ["SandboxesResource", "AsyncSandboxesResource"]


class SandboxesResource(SyncAPIResource):
    @cached_property
    def boxes(self) -> BoxesResource:
        return BoxesResource(self._client)

    @cached_property
    def registries(self) -> RegistriesResource:
        return RegistriesResource(self._client)

    @cached_property
    def snapshots(self) -> SnapshotsResource:
        return SnapshotsResource(self._client)

    @cached_property
    def with_raw_response(self) -> SandboxesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return SandboxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SandboxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return SandboxesResourceWithStreamingResponse(self)

    def list_usage_costs(
        self,
        *,
        end_time: Union[str, datetime],
        start_time: Union[str, datetime],
        cursor: str | Omit = omit,
        granularity: Literal["HOUR", "RESOURCE"] | Omit = omit,
        page_size: int | Omit = omit,
        resource_ids: SequenceNotStr[str] | Omit = omit,
        resource_type: Literal["SANDBOX", "SNAPSHOT"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorGetPagination[SandboxListUsageCostsResponse]:
        """
        Returns priced usage per sandbox or snapshot and UTC hour in the half-open
        requested interval. LCU uses the recorded compute amount for sandboxes;
        snapshots have zero LCU. LSU allocates the recorded workspace storage amount
        proportionally to attributed bytes, including checkpoints on their sandbox and
        snapshots as separate resources. Resource filters preserve each resource's
        share. Rate changes do not reprice recorded amounts. An access-filtered page can
        have no items and a non-null next_cursor; continue until next_cursor is null.

        Args:
          end_time: Exclusive RFC3339 end time; the range must not exceed 31 days

          start_time: Inclusive RFC3339 start time

          cursor: Opaque pagination cursor

          granularity: HOUR returns hourly buckets. RESOURCE sums each resource over the requested
              interval and sets period_start to start_time.

          page_size: Maximum rows to return

          resource_ids: Resource UUID filter; repeat this parameter up to 100 times

          resource_type: Resource type filter

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v2/sandboxes/usage/costs",
            page=SyncItemsCursorGetPagination[SandboxListUsageCostsResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "end_time": end_time,
                        "start_time": start_time,
                        "cursor": cursor,
                        "granularity": granularity,
                        "page_size": page_size,
                        "resource_ids": resource_ids,
                        "resource_type": resource_type,
                    },
                    sandbox_list_usage_costs_params.SandboxListUsageCostsParams,
                ),
            ),
            model=SandboxListUsageCostsResponse,
        )


class AsyncSandboxesResource(AsyncAPIResource):
    @cached_property
    def boxes(self) -> AsyncBoxesResource:
        return AsyncBoxesResource(self._client)

    @cached_property
    def registries(self) -> AsyncRegistriesResource:
        return AsyncRegistriesResource(self._client)

    @cached_property
    def snapshots(self) -> AsyncSnapshotsResource:
        return AsyncSnapshotsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncSandboxesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSandboxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSandboxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return AsyncSandboxesResourceWithStreamingResponse(self)

    def list_usage_costs(
        self,
        *,
        end_time: Union[str, datetime],
        start_time: Union[str, datetime],
        cursor: str | Omit = omit,
        granularity: Literal["HOUR", "RESOURCE"] | Omit = omit,
        page_size: int | Omit = omit,
        resource_ids: SequenceNotStr[str] | Omit = omit,
        resource_type: Literal["SANDBOX", "SNAPSHOT"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[SandboxListUsageCostsResponse, AsyncItemsCursorGetPagination[SandboxListUsageCostsResponse]]:
        """
        Returns priced usage per sandbox or snapshot and UTC hour in the half-open
        requested interval. LCU uses the recorded compute amount for sandboxes;
        snapshots have zero LCU. LSU allocates the recorded workspace storage amount
        proportionally to attributed bytes, including checkpoints on their sandbox and
        snapshots as separate resources. Resource filters preserve each resource's
        share. Rate changes do not reprice recorded amounts. An access-filtered page can
        have no items and a non-null next_cursor; continue until next_cursor is null.

        Args:
          end_time: Exclusive RFC3339 end time; the range must not exceed 31 days

          start_time: Inclusive RFC3339 start time

          cursor: Opaque pagination cursor

          granularity: HOUR returns hourly buckets. RESOURCE sums each resource over the requested
              interval and sets period_start to start_time.

          page_size: Maximum rows to return

          resource_ids: Resource UUID filter; repeat this parameter up to 100 times

          resource_type: Resource type filter

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v2/sandboxes/usage/costs",
            page=AsyncItemsCursorGetPagination[SandboxListUsageCostsResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "end_time": end_time,
                        "start_time": start_time,
                        "cursor": cursor,
                        "granularity": granularity,
                        "page_size": page_size,
                        "resource_ids": resource_ids,
                        "resource_type": resource_type,
                    },
                    sandbox_list_usage_costs_params.SandboxListUsageCostsParams,
                ),
            ),
            model=SandboxListUsageCostsResponse,
        )


class SandboxesResourceWithRawResponse:
    def __init__(self, sandboxes: SandboxesResource) -> None:
        self._sandboxes = sandboxes

        self.list_usage_costs = to_raw_response_wrapper(
            sandboxes.list_usage_costs,
        )

    @cached_property
    def boxes(self) -> BoxesResourceWithRawResponse:
        return BoxesResourceWithRawResponse(self._sandboxes.boxes)

    @cached_property
    def registries(self) -> RegistriesResourceWithRawResponse:
        return RegistriesResourceWithRawResponse(self._sandboxes.registries)

    @cached_property
    def snapshots(self) -> SnapshotsResourceWithRawResponse:
        return SnapshotsResourceWithRawResponse(self._sandboxes.snapshots)


class AsyncSandboxesResourceWithRawResponse:
    def __init__(self, sandboxes: AsyncSandboxesResource) -> None:
        self._sandboxes = sandboxes

        self.list_usage_costs = async_to_raw_response_wrapper(
            sandboxes.list_usage_costs,
        )

    @cached_property
    def boxes(self) -> AsyncBoxesResourceWithRawResponse:
        return AsyncBoxesResourceWithRawResponse(self._sandboxes.boxes)

    @cached_property
    def registries(self) -> AsyncRegistriesResourceWithRawResponse:
        return AsyncRegistriesResourceWithRawResponse(self._sandboxes.registries)

    @cached_property
    def snapshots(self) -> AsyncSnapshotsResourceWithRawResponse:
        return AsyncSnapshotsResourceWithRawResponse(self._sandboxes.snapshots)


class SandboxesResourceWithStreamingResponse:
    def __init__(self, sandboxes: SandboxesResource) -> None:
        self._sandboxes = sandboxes

        self.list_usage_costs = to_streamed_response_wrapper(
            sandboxes.list_usage_costs,
        )

    @cached_property
    def boxes(self) -> BoxesResourceWithStreamingResponse:
        return BoxesResourceWithStreamingResponse(self._sandboxes.boxes)

    @cached_property
    def registries(self) -> RegistriesResourceWithStreamingResponse:
        return RegistriesResourceWithStreamingResponse(self._sandboxes.registries)

    @cached_property
    def snapshots(self) -> SnapshotsResourceWithStreamingResponse:
        return SnapshotsResourceWithStreamingResponse(self._sandboxes.snapshots)


class AsyncSandboxesResourceWithStreamingResponse:
    def __init__(self, sandboxes: AsyncSandboxesResource) -> None:
        self._sandboxes = sandboxes

        self.list_usage_costs = async_to_streamed_response_wrapper(
            sandboxes.list_usage_costs,
        )

    @cached_property
    def boxes(self) -> AsyncBoxesResourceWithStreamingResponse:
        return AsyncBoxesResourceWithStreamingResponse(self._sandboxes.boxes)

    @cached_property
    def registries(self) -> AsyncRegistriesResourceWithStreamingResponse:
        return AsyncRegistriesResourceWithStreamingResponse(self._sandboxes.registries)

    @cached_property
    def snapshots(self) -> AsyncSnapshotsResourceWithStreamingResponse:
        return AsyncSnapshotsResourceWithStreamingResponse(self._sandboxes.snapshots)
