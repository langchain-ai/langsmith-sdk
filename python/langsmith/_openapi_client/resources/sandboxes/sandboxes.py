# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from .boxes import (
    BoxesResource,
    AsyncBoxesResource,
    BoxesResourceWithRawResponse,
    AsyncBoxesResourceWithRawResponse,
    BoxesResourceWithStreamingResponse,
    AsyncBoxesResourceWithStreamingResponse,
)
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
        """
        return SandboxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SandboxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return SandboxesResourceWithStreamingResponse(self)


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
        """
        return AsyncSandboxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSandboxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncSandboxesResourceWithStreamingResponse(self)


class SandboxesResourceWithRawResponse:
    def __init__(self, sandboxes: SandboxesResource) -> None:
        self._sandboxes = sandboxes

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

    @cached_property
    def boxes(self) -> AsyncBoxesResourceWithStreamingResponse:
        return AsyncBoxesResourceWithStreamingResponse(self._sandboxes.boxes)

    @cached_property
    def registries(self) -> AsyncRegistriesResourceWithStreamingResponse:
        return AsyncRegistriesResourceWithStreamingResponse(self._sandboxes.registries)

    @cached_property
    def snapshots(self) -> AsyncSnapshotsResourceWithStreamingResponse:
        return AsyncSnapshotsResourceWithStreamingResponse(self._sandboxes.snapshots)
