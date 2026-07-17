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
from ...types.runs import share_create_params, share_delete_params
from ..._base_client import make_request_options
from ...types.runs.share_create_response import ShareCreateResponse

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
        run_id: str,
        *,
        session_id: str | Omit = omit,
        trace_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareCreateResponse:
        """Creates or returns a share token for a run.

        Child runs share their trace root.

        Args:
          session_id: session_id is the tracing project UUID containing the trace.

          trace_id: trace_id is the root trace UUID to share.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return self._post(
            path_template("/v2/runs/{run_id}/share", run_id=run_id),
            body=maybe_transform(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                },
                share_create_params.ShareCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ShareCreateResponse,
        )

    def delete(
        self,
        trace_id: str,
        *,
        session_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Deletes the share token for the trace identified by trace_id and session_id.
        Idempotent: returns 204 whether or not a share token existed.

        Args:
          session_id: session_id is the tracing project UUID containing the trace.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not trace_id:
            raise ValueError(f"Expected a non-empty value for `trace_id` but received {trace_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template("/v2/runs/{trace_id}/share", trace_id=trace_id),
            body=maybe_transform({"session_id": session_id}, share_delete_params.ShareDeleteParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
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
        run_id: str,
        *,
        session_id: str | Omit = omit,
        trace_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ShareCreateResponse:
        """Creates or returns a share token for a run.

        Child runs share their trace root.

        Args:
          session_id: session_id is the tracing project UUID containing the trace.

          trace_id: trace_id is the root trace UUID to share.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return await self._post(
            path_template("/v2/runs/{run_id}/share", run_id=run_id),
            body=await async_maybe_transform(
                {
                    "session_id": session_id,
                    "trace_id": trace_id,
                },
                share_create_params.ShareCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ShareCreateResponse,
        )

    async def delete(
        self,
        trace_id: str,
        *,
        session_id: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Deletes the share token for the trace identified by trace_id and session_id.
        Idempotent: returns 204 whether or not a share token existed.

        Args:
          session_id: session_id is the tracing project UUID containing the trace.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not trace_id:
            raise ValueError(f"Expected a non-empty value for `trace_id` but received {trace_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template("/v2/runs/{trace_id}/share", trace_id=trace_id),
            body=await async_maybe_transform({"session_id": session_id}, share_delete_params.ShareDeleteParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )


class ShareResourceWithRawResponse:
    def __init__(self, share: ShareResource) -> None:
        self._share = share

        self.create = to_raw_response_wrapper(
            share.create,
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
        self.delete = async_to_raw_response_wrapper(
            share.delete,
        )


class ShareResourceWithStreamingResponse:
    def __init__(self, share: ShareResource) -> None:
        self._share = share

        self.create = to_streamed_response_wrapper(
            share.create,
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
        self.delete = async_to_streamed_response_wrapper(
            share.delete,
        )
