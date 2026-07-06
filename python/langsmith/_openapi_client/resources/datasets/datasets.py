# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from .experiment_runs import (
    ExperimentRunsResource,
    AsyncExperimentRunsResource,
    ExperimentRunsResourceWithRawResponse,
    AsyncExperimentRunsResourceWithRawResponse,
    ExperimentRunsResourceWithStreamingResponse,
    AsyncExperimentRunsResourceWithStreamingResponse,
)

__all__ = ["DatasetsResource", "AsyncDatasetsResource"]


class DatasetsResource(SyncAPIResource):
    @cached_property
    def experiment_runs(self) -> ExperimentRunsResource:
        return ExperimentRunsResource(self._client)

    @cached_property
    def with_raw_response(self) -> DatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return DatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return DatasetsResourceWithStreamingResponse(self)


class AsyncDatasetsResource(AsyncAPIResource):
    @cached_property
    def experiment_runs(self) -> AsyncExperimentRunsResource:
        return AsyncExperimentRunsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncDatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return AsyncDatasetsResourceWithStreamingResponse(self)


class DatasetsResourceWithRawResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

    @cached_property
    def experiment_runs(self) -> ExperimentRunsResourceWithRawResponse:
        return ExperimentRunsResourceWithRawResponse(self._datasets.experiment_runs)


class AsyncDatasetsResourceWithRawResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

    @cached_property
    def experiment_runs(self) -> AsyncExperimentRunsResourceWithRawResponse:
        return AsyncExperimentRunsResourceWithRawResponse(self._datasets.experiment_runs)


class DatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

    @cached_property
    def experiment_runs(self) -> ExperimentRunsResourceWithStreamingResponse:
        return ExperimentRunsResourceWithStreamingResponse(self._datasets.experiment_runs)


class AsyncDatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

    @cached_property
    def experiment_runs(self) -> AsyncExperimentRunsResourceWithStreamingResponse:
        return AsyncExperimentRunsResourceWithStreamingResponse(self._datasets.experiment_runs)
