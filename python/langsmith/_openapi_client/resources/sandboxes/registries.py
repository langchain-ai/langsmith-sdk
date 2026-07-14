# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..._types import Body, Omit, Query, Headers, NoneType, NotGiven, omit, not_given
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
from ...types.sandboxes import registry_list_params, registry_create_params, registry_update_params
from ...types.sandboxes.registry_response import RegistryResponse
from ...types.sandboxes.registry_list_response import RegistryListResponse

__all__ = ["RegistriesResource", "AsyncRegistriesResource"]


class RegistriesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RegistriesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return RegistriesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RegistriesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return RegistriesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        name: str,
        password: str,
        url: str,
        username: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryResponse:
        """
        Create a sandbox registry for pulling private images.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/v2/sandboxes/registries",
            body=maybe_transform(
                {
                    "name": name,
                    "password": password,
                    "url": url,
                    "username": username,
                },
                registry_create_params.RegistryCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
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
    ) -> RegistryResponse:
        """
        Get a sandbox registry by name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return self._get(
            path_template("/v2/sandboxes/registries/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
        )

    def update(
        self,
        path_name: str,
        *,
        body_name: str | Omit = omit,
        password: str | Omit = omit,
        url: str | Omit = omit,
        username: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryResponse:
        """
        Update a sandbox registry's name and/or credentials.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return self._patch(
            path_template("/v2/sandboxes/registries/{path_name}", path_name=path_name),
            body=maybe_transform(
                {
                    "body_name": body_name,
                    "password": password,
                    "url": url,
                    "username": username,
                },
                registry_update_params.RegistryUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
        )

    def list(
        self,
        *,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryListResponse:
        """
        List sandbox registries for pulling private images.

        Args:
          limit: Maximum number of registries to return

          name_contains: Filter to registries whose name contains this substring

          offset: Number of registries to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/v2/sandboxes/registries",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                    },
                    registry_list_params.RegistryListParams,
                ),
            ),
            cast_to=RegistryListResponse,
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
        """
        Delete a sandbox registry by name.

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
            path_template("/v2/sandboxes/registries/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class AsyncRegistriesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRegistriesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncRegistriesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRegistriesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncRegistriesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        name: str,
        password: str,
        url: str,
        username: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryResponse:
        """
        Create a sandbox registry for pulling private images.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/v2/sandboxes/registries",
            body=await async_maybe_transform(
                {
                    "name": name,
                    "password": password,
                    "url": url,
                    "username": username,
                },
                registry_create_params.RegistryCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
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
    ) -> RegistryResponse:
        """
        Get a sandbox registry by name.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not name:
            raise ValueError(f"Expected a non-empty value for `name` but received {name!r}")
        return await self._get(
            path_template("/v2/sandboxes/registries/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
        )

    async def update(
        self,
        path_name: str,
        *,
        body_name: str | Omit = omit,
        password: str | Omit = omit,
        url: str | Omit = omit,
        username: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryResponse:
        """
        Update a sandbox registry's name and/or credentials.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not path_name:
            raise ValueError(f"Expected a non-empty value for `path_name` but received {path_name!r}")
        return await self._patch(
            path_template("/v2/sandboxes/registries/{path_name}", path_name=path_name),
            body=await async_maybe_transform(
                {
                    "body_name": body_name,
                    "password": password,
                    "url": url,
                    "username": username,
                },
                registry_update_params.RegistryUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RegistryResponse,
        )

    async def list(
        self,
        *,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RegistryListResponse:
        """
        List sandbox registries for pulling private images.

        Args:
          limit: Maximum number of registries to return

          name_contains: Filter to registries whose name contains this substring

          offset: Number of registries to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/v2/sandboxes/registries",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                    },
                    registry_list_params.RegistryListParams,
                ),
            ),
            cast_to=RegistryListResponse,
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
        """
        Delete a sandbox registry by name.

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
            path_template("/v2/sandboxes/registries/{name}", name=name),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class RegistriesResourceWithRawResponse:
    def __init__(self, registries: RegistriesResource) -> None:
        self._registries = registries

        self.create = to_raw_response_wrapper(
            registries.create,
        )
        self.retrieve = to_raw_response_wrapper(
            registries.retrieve,
        )
        self.update = to_raw_response_wrapper(
            registries.update,
        )
        self.list = to_raw_response_wrapper(
            registries.list,
        )
        self.delete = to_raw_response_wrapper(
            registries.delete,
        )


class AsyncRegistriesResourceWithRawResponse:
    def __init__(self, registries: AsyncRegistriesResource) -> None:
        self._registries = registries

        self.create = async_to_raw_response_wrapper(
            registries.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            registries.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            registries.update,
        )
        self.list = async_to_raw_response_wrapper(
            registries.list,
        )
        self.delete = async_to_raw_response_wrapper(
            registries.delete,
        )


class RegistriesResourceWithStreamingResponse:
    def __init__(self, registries: RegistriesResource) -> None:
        self._registries = registries

        self.create = to_streamed_response_wrapper(
            registries.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            registries.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            registries.update,
        )
        self.list = to_streamed_response_wrapper(
            registries.list,
        )
        self.delete = to_streamed_response_wrapper(
            registries.delete,
        )


class AsyncRegistriesResourceWithStreamingResponse:
    def __init__(self, registries: AsyncRegistriesResource) -> None:
        self._registries = registries

        self.create = async_to_streamed_response_wrapper(
            registries.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            registries.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            registries.update,
        )
        self.list = async_to_streamed_response_wrapper(
            registries.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            registries.delete,
        )
