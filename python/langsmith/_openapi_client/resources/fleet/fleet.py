# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from .threads import (
    ThreadsResource,
    AsyncThreadsResource,
    ThreadsResourceWithRawResponse,
    AsyncThreadsResourceWithRawResponse,
    ThreadsResourceWithStreamingResponse,
    AsyncThreadsResourceWithStreamingResponse,
)
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource

__all__ = ["FleetResource", "AsyncFleetResource"]


class FleetResource(SyncAPIResource):
    @cached_property
    def threads(self) -> ThreadsResource:
        return ThreadsResource(self._client)

    @cached_property
    def with_raw_response(self) -> FleetResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return FleetResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> FleetResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return FleetResourceWithStreamingResponse(self)


class AsyncFleetResource(AsyncAPIResource):
    @cached_property
    def threads(self) -> AsyncThreadsResource:
        return AsyncThreadsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncFleetResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncFleetResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncFleetResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncFleetResourceWithStreamingResponse(self)


class FleetResourceWithRawResponse:
    def __init__(self, fleet: FleetResource) -> None:
        self._fleet = fleet

    @cached_property
    def threads(self) -> ThreadsResourceWithRawResponse:
        return ThreadsResourceWithRawResponse(self._fleet.threads)


class AsyncFleetResourceWithRawResponse:
    def __init__(self, fleet: AsyncFleetResource) -> None:
        self._fleet = fleet

    @cached_property
    def threads(self) -> AsyncThreadsResourceWithRawResponse:
        return AsyncThreadsResourceWithRawResponse(self._fleet.threads)


class FleetResourceWithStreamingResponse:
    def __init__(self, fleet: FleetResource) -> None:
        self._fleet = fleet

    @cached_property
    def threads(self) -> ThreadsResourceWithStreamingResponse:
        return ThreadsResourceWithStreamingResponse(self._fleet.threads)


class AsyncFleetResourceWithStreamingResponse:
    def __init__(self, fleet: AsyncFleetResource) -> None:
        self._fleet = fleet

    @cached_property
    def threads(self) -> AsyncThreadsResourceWithStreamingResponse:
        return AsyncThreadsResourceWithStreamingResponse(self._fleet.threads)
