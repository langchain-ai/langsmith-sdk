# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from .runs import (
    RunsResource,
    AsyncRunsResource,
    RunsResourceWithRawResponse,
    AsyncRunsResourceWithRawResponse,
    RunsResourceWithStreamingResponse,
    AsyncRunsResourceWithStreamingResponse,
)
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource

__all__ = ["TracesResource", "AsyncTracesResource"]


class TracesResource(SyncAPIResource):
    @cached_property
    def runs(self) -> RunsResource:
        return RunsResource(self._client)

    @cached_property
    def with_raw_response(self) -> TracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return TracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return TracesResourceWithStreamingResponse(self)


class AsyncTracesResource(AsyncAPIResource):
    @cached_property
    def runs(self) -> AsyncRunsResource:
        return AsyncRunsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncTracesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTracesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTracesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncTracesResourceWithStreamingResponse(self)


class TracesResourceWithRawResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

    @cached_property
    def runs(self) -> RunsResourceWithRawResponse:
        return RunsResourceWithRawResponse(self._traces.runs)


class AsyncTracesResourceWithRawResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

    @cached_property
    def runs(self) -> AsyncRunsResourceWithRawResponse:
        return AsyncRunsResourceWithRawResponse(self._traces.runs)


class TracesResourceWithStreamingResponse:
    def __init__(self, traces: TracesResource) -> None:
        self._traces = traces

    @cached_property
    def runs(self) -> RunsResourceWithStreamingResponse:
        return RunsResourceWithStreamingResponse(self._traces.runs)


class AsyncTracesResourceWithStreamingResponse:
    def __init__(self, traces: AsyncTracesResource) -> None:
        self._traces = traces

    @cached_property
    def runs(self) -> AsyncRunsResourceWithStreamingResponse:
        return AsyncRunsResourceWithStreamingResponse(self._traces.runs)
