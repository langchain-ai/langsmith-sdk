# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict

import httpx

from ..._types import Body, Omit, Query, Headers, NoneType, NotGiven, SequenceNotStr, omit, not_given
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
from ...types.sandboxes import (
    box_list_params,
    box_create_params,
    box_update_params,
    box_create_snapshot_params,
    box_generate_service_url_params,
)
from ...types.sandbox_response import SandboxResponse
from ...types.snapshot_response import SnapshotResponse
from ...types.service_url_response import ServiceURLResponse
from ...types.sandbox_list_response import SandboxListResponse
from ...types.sandbox_status_response import SandboxStatusResponse

__all__ = ["BoxesResource", "AsyncBoxesResource"]


class BoxesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> BoxesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return BoxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> BoxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return BoxesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        cpu_millicores: int | Omit = omit,
        delete_after_stop_seconds: int | Omit = omit,
        env_vars: Dict[str, str] | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        idle_ttl_seconds: int | Omit = omit,
        mem_bytes: int | Omit = omit,
        mount_config: box_create_params.MountConfig | Omit = omit,
        name: str | Omit = omit,
        proxy_config: box_create_params.ProxyConfig | Omit = omit,
        restore_memory: bool | Omit = omit,
        snapshot_id: str | Omit = omit,
        snapshot_name: str | Omit = omit,
        tag_value_ids: SequenceNotStr[str] | Omit = omit,
        vcpus: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Create a new sandbox from a snapshot.

        Provide at most one of `snapshot_id` or
        `snapshot_name`; if neither is provided, the server uses the default snapshot.

        Args:
          cpu_millicores: CPUMillicores optionally requests CPU at millicore granularity (e.g. 500 = 0.5
              vCPU); takes precedence over VCPUs. Fractional (sub-vCPU) values are not
              available for every sandbox.

          restore_memory:
              RestoreMemory selects how the sandbox handles a snapshot's captured memory:

              nil → if-present: resume from memory when the snapshot has it, else cold-boot
              (default). true → always: resume from memory; rejected if the snapshot has none.
              false → never: always cold-boot.

              Applies to this request only.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/v2/sandboxes/boxes",
            body=maybe_transform(
                {
                    "cpu_millicores": cpu_millicores,
                    "delete_after_stop_seconds": delete_after_stop_seconds,
                    "env_vars": env_vars,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "idle_ttl_seconds": idle_ttl_seconds,
                    "mem_bytes": mem_bytes,
                    "mount_config": mount_config,
                    "name": name,
                    "proxy_config": proxy_config,
                    "restore_memory": restore_memory,
                    "snapshot_id": snapshot_id,
                    "snapshot_name": snapshot_name,
                    "tag_value_ids": tag_value_ids,
                    "vcpus": vcpus,
                },
                box_create_params.BoxCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    def retrieve(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Retrieve a sandbox by name.

        Stale provisioning sandboxes are auto-failed.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._get(
            path_template("/v2/sandboxes/boxes/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    def update(
        self,
        path_name: str,
        *,
        cpu_millicores: int | Omit = omit,
        delete_after_stop_seconds: int | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        idle_ttl_seconds: int | Omit = omit,
        mem_bytes: int | Omit = omit,
        body_name: str | Omit = omit,
        proxy_config: box_update_params.ProxyConfig | Omit = omit,
        tag_value_ids: SequenceNotStr[str] | Omit = omit,
        vcpus: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Update a sandbox's display name.

        The name must be unique within the tenant.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return self._patch(
            path_template("/v2/sandboxes/boxes/{path_name}", path_name=path_name),
            body=maybe_transform(
                {
                    "cpu_millicores": cpu_millicores,
                    "delete_after_stop_seconds": delete_after_stop_seconds,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "idle_ttl_seconds": idle_ttl_seconds,
                    "mem_bytes": mem_bytes,
                    "body_name": body_name,
                    "proxy_config": proxy_config,
                    "tag_value_ids": tag_value_ids,
                    "vcpus": vcpus,
                },
                box_update_params.BoxUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    def list(
        self,
        *,
        created_by: str | Omit = omit,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        sort_by: str | Omit = omit,
        sort_direction: str | Omit = omit,
        status: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxListResponse:
        """
        List sandboxes for the authenticated tenant, with optional filtering, sorting,
        and pagination.

        Args:
          created_by: Filter by creator identity. Only 'me' is supported.

          limit: Maximum number of results

          name_contains: Filter by name substring

          offset: Pagination offset

          sort_by: Sort column (name, status, created_at)

          sort_direction: Sort direction (asc, desc)

          status: Filter by status (provisioning, ready, failed, stopped, deleting)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/v2/sandboxes/boxes",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "created_by": created_by,
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_direction": sort_direction,
                        "status": status,
                    },
                    box_list_params.BoxListParams,
                ),
            ),
            cast_to=SandboxListResponse,
        )

    def delete(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Delete a sandbox by name or UUID.

        Tears down the sandbox runtime and removes the
        DB record.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template("/v2/sandboxes/boxes/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    def create_snapshot(
        self,
        path_name: str,
        *,
        body_name: str,
        checkpoint: str | Omit = omit,
        docker_image: str | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        include_memory: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SnapshotResponse:
        """
        Create a snapshot by capturing the current state of a sandbox or promoting an
        existing checkpoint.

        Args:
          checkpoint: if omitted, creates a fresh checkpoint from the running VM

          docker_image: sandbox-local Docker image to export

          fs_capacity_bytes: required for Docker image export unless the sandbox has a capacity

          include_memory: IncludeMemory, when true, captures a full VM memory snapshot alongside the
              filesystem clone. Only honored when the sandbox is running AND Checkpoint is
              omitted (i.e. a fresh in-VM checkpoint is requested). Defaults to false to keep
              snapshots small unless memory restore is explicitly desired.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return self._post(
            path_template("/v2/sandboxes/boxes/{path_name}/snapshot", path_name=path_name),
            body=maybe_transform(
                {
                    "body_name": body_name,
                    "checkpoint": checkpoint,
                    "docker_image": docker_image,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "include_memory": include_memory,
                },
                box_create_snapshot_params.BoxCreateSnapshotParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SnapshotResponse,
        )

    def generate_service_url(
        self,
        name: str,
        *,
        expires_in_seconds: int | Omit = omit,
        port: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServiceURLResponse:
        """
        Create a short-lived JWT for accessing an HTTP service running on a specific
        port inside a sandbox. Returns a browser_url (sets auth cookie via redirect), a
        service_url (for use with the X-Langsmith-Sandbox-Service-Token header), the raw
        token, and its expiry.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._post(
            path_template("/v2/sandboxes/boxes/{name}/service-url", name=name),
            body=maybe_transform(
                {
                    "expires_in_seconds": expires_in_seconds,
                    "port": port,
                },
                box_generate_service_url_params.BoxGenerateServiceURLParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServiceURLResponse,
        )

    def get_status(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxStatusResponse:
        """
        Retrieve the lightweight status of a sandbox for polling.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._get(
            path_template("/v2/sandboxes/boxes/{name}/status", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxStatusResponse,
        )

    def start(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Start a stopped or failed sandbox.

        This endpoint is not idempotent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._post(
            path_template("/v2/sandboxes/boxes/{name}/start", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    def stop(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Stop a ready sandbox.

        This endpoint is not idempotent; the filesystem is
        preserved for later restart.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._post(
            path_template("/v2/sandboxes/boxes/{name}/stop", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class AsyncBoxesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncBoxesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncBoxesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncBoxesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncBoxesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        cpu_millicores: int | Omit = omit,
        delete_after_stop_seconds: int | Omit = omit,
        env_vars: Dict[str, str] | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        idle_ttl_seconds: int | Omit = omit,
        mem_bytes: int | Omit = omit,
        mount_config: box_create_params.MountConfig | Omit = omit,
        name: str | Omit = omit,
        proxy_config: box_create_params.ProxyConfig | Omit = omit,
        restore_memory: bool | Omit = omit,
        snapshot_id: str | Omit = omit,
        snapshot_name: str | Omit = omit,
        tag_value_ids: SequenceNotStr[str] | Omit = omit,
        vcpus: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Create a new sandbox from a snapshot.

        Provide at most one of `snapshot_id` or
        `snapshot_name`; if neither is provided, the server uses the default snapshot.

        Args:
          cpu_millicores: CPUMillicores optionally requests CPU at millicore granularity (e.g. 500 = 0.5
              vCPU); takes precedence over VCPUs. Fractional (sub-vCPU) values are not
              available for every sandbox.

          restore_memory:
              RestoreMemory selects how the sandbox handles a snapshot's captured memory:

              nil → if-present: resume from memory when the snapshot has it, else cold-boot
              (default). true → always: resume from memory; rejected if the snapshot has none.
              false → never: always cold-boot.

              Applies to this request only.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/v2/sandboxes/boxes",
            body=await async_maybe_transform(
                {
                    "cpu_millicores": cpu_millicores,
                    "delete_after_stop_seconds": delete_after_stop_seconds,
                    "env_vars": env_vars,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "idle_ttl_seconds": idle_ttl_seconds,
                    "mem_bytes": mem_bytes,
                    "mount_config": mount_config,
                    "name": name,
                    "proxy_config": proxy_config,
                    "restore_memory": restore_memory,
                    "snapshot_id": snapshot_id,
                    "snapshot_name": snapshot_name,
                    "tag_value_ids": tag_value_ids,
                    "vcpus": vcpus,
                },
                box_create_params.BoxCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    async def retrieve(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Retrieve a sandbox by name.

        Stale provisioning sandboxes are auto-failed.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._get(
            path_template("/v2/sandboxes/boxes/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    async def update(
        self,
        path_name: str,
        *,
        cpu_millicores: int | Omit = omit,
        delete_after_stop_seconds: int | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        idle_ttl_seconds: int | Omit = omit,
        mem_bytes: int | Omit = omit,
        body_name: str | Omit = omit,
        proxy_config: box_update_params.ProxyConfig | Omit = omit,
        tag_value_ids: SequenceNotStr[str] | Omit = omit,
        vcpus: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Update a sandbox's display name.

        The name must be unique within the tenant.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return await self._patch(
            path_template("/v2/sandboxes/boxes/{path_name}", path_name=path_name),
            body=await async_maybe_transform(
                {
                    "cpu_millicores": cpu_millicores,
                    "delete_after_stop_seconds": delete_after_stop_seconds,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "idle_ttl_seconds": idle_ttl_seconds,
                    "mem_bytes": mem_bytes,
                    "body_name": body_name,
                    "proxy_config": proxy_config,
                    "tag_value_ids": tag_value_ids,
                    "vcpus": vcpus,
                },
                box_update_params.BoxUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    async def list(
        self,
        *,
        created_by: str | Omit = omit,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        sort_by: str | Omit = omit,
        sort_direction: str | Omit = omit,
        status: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxListResponse:
        """
        List sandboxes for the authenticated tenant, with optional filtering, sorting,
        and pagination.

        Args:
          created_by: Filter by creator identity. Only 'me' is supported.

          limit: Maximum number of results

          name_contains: Filter by name substring

          offset: Pagination offset

          sort_by: Sort column (name, status, created_at)

          sort_direction: Sort direction (asc, desc)

          status: Filter by status (provisioning, ready, failed, stopped, deleting)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/v2/sandboxes/boxes",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "created_by": created_by,
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_direction": sort_direction,
                        "status": status,
                    },
                    box_list_params.BoxListParams,
                ),
            ),
            cast_to=SandboxListResponse,
        )

    async def delete(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Delete a sandbox by name or UUID.

        Tears down the sandbox runtime and removes the
        DB record.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template("/v2/sandboxes/boxes/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    async def create_snapshot(
        self,
        path_name: str,
        *,
        body_name: str,
        checkpoint: str | Omit = omit,
        docker_image: str | Omit = omit,
        fs_capacity_bytes: int | Omit = omit,
        include_memory: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SnapshotResponse:
        """
        Create a snapshot by capturing the current state of a sandbox or promoting an
        existing checkpoint.

        Args:
          checkpoint: if omitted, creates a fresh checkpoint from the running VM

          docker_image: sandbox-local Docker image to export

          fs_capacity_bytes: required for Docker image export unless the sandbox has a capacity

          include_memory: IncludeMemory, when true, captures a full VM memory snapshot alongside the
              filesystem clone. Only honored when the sandbox is running AND Checkpoint is
              omitted (i.e. a fresh in-VM checkpoint is requested). Defaults to false to keep
              snapshots small unless memory restore is explicitly desired.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return await self._post(
            path_template("/v2/sandboxes/boxes/{path_name}/snapshot", path_name=path_name),
            body=await async_maybe_transform(
                {
                    "body_name": body_name,
                    "checkpoint": checkpoint,
                    "docker_image": docker_image,
                    "fs_capacity_bytes": fs_capacity_bytes,
                    "include_memory": include_memory,
                },
                box_create_snapshot_params.BoxCreateSnapshotParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SnapshotResponse,
        )

    async def generate_service_url(
        self,
        name: str,
        *,
        expires_in_seconds: int | Omit = omit,
        port: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServiceURLResponse:
        """
        Create a short-lived JWT for accessing an HTTP service running on a specific
        port inside a sandbox. Returns a browser_url (sets auth cookie via redirect), a
        service_url (for use with the X-Langsmith-Sandbox-Service-Token header), the raw
        token, and its expiry.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._post(
            path_template("/v2/sandboxes/boxes/{name}/service-url", name=name),
            body=await async_maybe_transform(
                {
                    "expires_in_seconds": expires_in_seconds,
                    "port": port,
                },
                box_generate_service_url_params.BoxGenerateServiceURLParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServiceURLResponse,
        )

    async def get_status(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxStatusResponse:
        """
        Retrieve the lightweight status of a sandbox for polling.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._get(
            path_template("/v2/sandboxes/boxes/{name}/status", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxStatusResponse,
        )

    async def start(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SandboxResponse:
        """Start a stopped or failed sandbox.

        This endpoint is not idempotent.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._post(
            path_template("/v2/sandboxes/boxes/{name}/start", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SandboxResponse,
        )

    async def stop(
        self,
        name: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Stop a ready sandbox.

        This endpoint is not idempotent; the filesystem is
        preserved for later restart.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._post(
            path_template("/v2/sandboxes/boxes/{name}/stop", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class BoxesResourceWithRawResponse:
    def __init__(self, boxes: BoxesResource) -> None:
        self._boxes = boxes

        self.create = to_raw_response_wrapper(
            boxes.create,
        )
        self.retrieve = to_raw_response_wrapper(
            boxes.retrieve,
        )
        self.update = to_raw_response_wrapper(
            boxes.update,
        )
        self.list = to_raw_response_wrapper(
            boxes.list,
        )
        self.delete = to_raw_response_wrapper(
            boxes.delete,
        )
        self.create_snapshot = to_raw_response_wrapper(
            boxes.create_snapshot,
        )
        self.generate_service_url = to_raw_response_wrapper(
            boxes.generate_service_url,
        )
        self.get_status = to_raw_response_wrapper(
            boxes.get_status,
        )
        self.start = to_raw_response_wrapper(
            boxes.start,
        )
        self.stop = to_raw_response_wrapper(
            boxes.stop,
        )


class AsyncBoxesResourceWithRawResponse:
    def __init__(self, boxes: AsyncBoxesResource) -> None:
        self._boxes = boxes

        self.create = async_to_raw_response_wrapper(
            boxes.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            boxes.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            boxes.update,
        )
        self.list = async_to_raw_response_wrapper(
            boxes.list,
        )
        self.delete = async_to_raw_response_wrapper(
            boxes.delete,
        )
        self.create_snapshot = async_to_raw_response_wrapper(
            boxes.create_snapshot,
        )
        self.generate_service_url = async_to_raw_response_wrapper(
            boxes.generate_service_url,
        )
        self.get_status = async_to_raw_response_wrapper(
            boxes.get_status,
        )
        self.start = async_to_raw_response_wrapper(
            boxes.start,
        )
        self.stop = async_to_raw_response_wrapper(
            boxes.stop,
        )


class BoxesResourceWithStreamingResponse:
    def __init__(self, boxes: BoxesResource) -> None:
        self._boxes = boxes

        self.create = to_streamed_response_wrapper(
            boxes.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            boxes.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            boxes.update,
        )
        self.list = to_streamed_response_wrapper(
            boxes.list,
        )
        self.delete = to_streamed_response_wrapper(
            boxes.delete,
        )
        self.create_snapshot = to_streamed_response_wrapper(
            boxes.create_snapshot,
        )
        self.generate_service_url = to_streamed_response_wrapper(
            boxes.generate_service_url,
        )
        self.get_status = to_streamed_response_wrapper(
            boxes.get_status,
        )
        self.start = to_streamed_response_wrapper(
            boxes.start,
        )
        self.stop = to_streamed_response_wrapper(
            boxes.stop,
        )


class AsyncBoxesResourceWithStreamingResponse:
    def __init__(self, boxes: AsyncBoxesResource) -> None:
        self._boxes = boxes

        self.create = async_to_streamed_response_wrapper(
            boxes.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            boxes.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            boxes.update,
        )
        self.list = async_to_streamed_response_wrapper(
            boxes.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            boxes.delete,
        )
        self.create_snapshot = async_to_streamed_response_wrapper(
            boxes.create_snapshot,
        )
        self.generate_service_url = async_to_streamed_response_wrapper(
            boxes.generate_service_url,
        )
        self.get_status = async_to_streamed_response_wrapper(
            boxes.get_status,
        )
        self.start = async_to_streamed_response_wrapper(
            boxes.start,
        )
        self.stop = async_to_streamed_response_wrapper(
            boxes.stop,
        )
