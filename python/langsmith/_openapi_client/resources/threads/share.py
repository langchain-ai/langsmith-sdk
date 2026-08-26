# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from ..._httpx import httpx
from ..._types import Body, Query, Headers, NoneType, NotGiven, not_given
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
from ...types.threads import share_create_params, share_delete_params, share_retrieve_params
from ...types.threads.share_create_response import ShareCreateResponse
from ...types.threads.share_retrieve_response import ShareRetrieveResponse

__all__ = ["ShareResource", "AsyncShareResource"]


class ShareResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ShareResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return ShareResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ShareResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return ShareResourceWithStreamingResponse(self)

    def create(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareCreateResponse:
        """Mints a public share token for a thread.

        Idempotent: sharing an already-shared
        thread returns the existing token.

        Args:
          project_id: project_id is the tracing project UUID containing the thread.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return self._post(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            body=maybe_transform({"project_id": project_id}, share_create_params.ShareCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ShareCreateResponse,
        )

    def retrieve(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareRetrieveResponse:
        """Returns the share token for a thread, or 404 when it is not shared.

        Gated on
        runs:share so the control's state matches the control's permission.

        Args:
          project_id: Project UUID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return self._get(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"project_id": project_id}, share_retrieve_params.ShareRetrieveParams),
            ),
            cast_to=ShareRetrieveResponse,
        )

    def delete(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Deletes the share token for a thread.

        Idempotent: returns 204 whether or not a
        share token existed. Deliberately does not verify the thread still exists.

        Args:
          project_id: Project UUID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"project_id": project_id}, share_delete_params.ShareDeleteParams),
            ),
            cast_to=NoneType,
        )


class AsyncShareResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncShareResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncShareResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncShareResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncShareResourceWithStreamingResponse(self)

    async def create(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareCreateResponse:
        """Mints a public share token for a thread.

        Idempotent: sharing an already-shared
        thread returns the existing token.

        Args:
          project_id: project_id is the tracing project UUID containing the thread.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return await self._post(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            body=await async_maybe_transform({"project_id": project_id}, share_create_params.ShareCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ShareCreateResponse,
        )

    async def retrieve(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareRetrieveResponse:
        """Returns the share token for a thread, or 404 when it is not shared.

        Gated on
        runs:share so the control's state matches the control's permission.

        Args:
          project_id: Project UUID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        return await self._get(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"project_id": project_id}, share_retrieve_params.ShareRetrieveParams
                ),
            ),
            cast_to=ShareRetrieveResponse,
        )

    async def delete(
        self,
        thread_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Deletes the share token for a thread.

        Idempotent: returns 204 whether or not a
        share token existed. Deliberately does not verify the thread still exists.

        Args:
          project_id: Project UUID

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not thread_id:
            raise ValueError(f"Expected a non-empty value for `thread_id` but received {thread_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template("/api/v2/threads/{thread_id}/share", thread_id=thread_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"project_id": project_id}, share_delete_params.ShareDeleteParams),
            ),
            cast_to=NoneType,
        )


class ShareResourceWithRawResponse:
    def __init__(self, share: ShareResource) -> None:
        self._share = share

        self.create = to_raw_response_wrapper(
            share.create,
        )
        self.retrieve = to_raw_response_wrapper(
            share.retrieve,
        )
        self.delete = to_raw_response_wrapper(
            share.delete,
        )


class AsyncShareResourceWithRawResponse:
    def __init__(self, share: AsyncShareResource) -> None:
        self._share = share

        self.create = async_to_raw_response_wrapper(
            share.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            share.retrieve,
        )
        self.delete = async_to_raw_response_wrapper(
            share.delete,
        )


class ShareResourceWithStreamingResponse:
    def __init__(self, share: ShareResource) -> None:
        self._share = share

        self.create = to_streamed_response_wrapper(
            share.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            share.retrieve,
        )
        self.delete = to_streamed_response_wrapper(
            share.delete,
        )


class AsyncShareResourceWithStreamingResponse:
    def __init__(self, share: AsyncShareResource) -> None:
        self._share = share

        self.create = async_to_streamed_response_wrapper(
            share.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            share.retrieve,
        )
        self.delete = async_to_streamed_response_wrapper(
            share.delete,
        )
