# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from .secrets.secrets import (
    SecretsResource,
    AsyncSecretsResource,
    SecretsResourceWithRawResponse,
    AsyncSecretsResourceWithRawResponse,
    SecretsResourceWithStreamingResponse,
    AsyncSecretsResourceWithStreamingResponse,
)

__all__ = ["WorkspacesResource", "AsyncWorkspacesResource"]


class WorkspacesResource(SyncAPIResource):
    @cached_property
    def secrets(self) -> SecretsResource:
        return SecretsResource(self._client)

    @cached_property
    def with_raw_response(self) -> WorkspacesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return WorkspacesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> WorkspacesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return WorkspacesResourceWithStreamingResponse(self)


class AsyncWorkspacesResource(AsyncAPIResource):
    @cached_property
    def secrets(self) -> AsyncSecretsResource:
        return AsyncSecretsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncWorkspacesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncWorkspacesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncWorkspacesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncWorkspacesResourceWithStreamingResponse(self)


class WorkspacesResourceWithRawResponse:
    def __init__(self, workspaces: WorkspacesResource) -> None:
        self._workspaces = workspaces

    @cached_property
    def secrets(self) -> SecretsResourceWithRawResponse:
        return SecretsResourceWithRawResponse(self._workspaces.secrets)


class AsyncWorkspacesResourceWithRawResponse:
    def __init__(self, workspaces: AsyncWorkspacesResource) -> None:
        self._workspaces = workspaces

    @cached_property
    def secrets(self) -> AsyncSecretsResourceWithRawResponse:
        return AsyncSecretsResourceWithRawResponse(self._workspaces.secrets)


class WorkspacesResourceWithStreamingResponse:
    def __init__(self, workspaces: WorkspacesResource) -> None:
        self._workspaces = workspaces

    @cached_property
    def secrets(self) -> SecretsResourceWithStreamingResponse:
        return SecretsResourceWithStreamingResponse(self._workspaces.secrets)


class AsyncWorkspacesResourceWithStreamingResponse:
    def __init__(self, workspaces: AsyncWorkspacesResource) -> None:
        self._workspaces = workspaces

    @cached_property
    def secrets(self) -> AsyncSecretsResourceWithStreamingResponse:
        return AsyncSecretsResourceWithStreamingResponse(self._workspaces.secrets)
