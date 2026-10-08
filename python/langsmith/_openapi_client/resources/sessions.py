# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal

from ..types import session_resolve_params
from .._httpx import httpx
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options
from ..types.session_resolve_response import SessionResolveResponse

__all__ = ["SessionsResource", "AsyncSessionsResource"]


class SessionsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SessionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return SessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SessionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return SessionsResourceWithStreamingResponse(self)

    def resolve(
        self,
        *,
        kind: Literal["AGENT", "EXPERIMENT", "EVALUATOR"],
        id: str | Omit = omit,
        environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionResolveResponse:
        """
        **Beta:** This endpoint is in active development and may change without notice.
        Returns the tracing project (session) an address names. An address is an AGENT
        (`id` and `environment`), an EXPERIMENT (`id`), or an EVALUATOR (no `id`:
        evaluator traces share one project per workspace). Send `kind` and `environment`
        in upper case, as listed; they are matched case-insensitively, while the Agent
        `id` is case-sensitive. An address that does not exist, or whose project you
        cannot read, is a 404. Pass the returned `session_id` to any endpoint that takes
        a project (session) ID. This is not supported on a BYOC data plane yet, and is a
        501 there.

        Args:
          kind: The kind of address.

          id: The Agent's user-assigned id for AGENT, or the experiment's id for EXPERIMENT.
              Not set for EVALUATOR.

          environment: The Agent environment. Only set for AGENT.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/api/v1/sessions/resolutions",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "kind": kind,
                        "id": id,
                        "environment": environment,
                    },
                    session_resolve_params.SessionResolveParams,
                ),
            ),
            cast_to=SessionResolveResponse,
        )


class AsyncSessionsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSessionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSessionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return AsyncSessionsResourceWithStreamingResponse(self)

    async def resolve(
        self,
        *,
        kind: Literal["AGENT", "EXPERIMENT", "EVALUATOR"],
        id: str | Omit = omit,
        environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SessionResolveResponse:
        """
        **Beta:** This endpoint is in active development and may change without notice.
        Returns the tracing project (session) an address names. An address is an AGENT
        (`id` and `environment`), an EXPERIMENT (`id`), or an EVALUATOR (no `id`:
        evaluator traces share one project per workspace). Send `kind` and `environment`
        in upper case, as listed; they are matched case-insensitively, while the Agent
        `id` is case-sensitive. An address that does not exist, or whose project you
        cannot read, is a 404. Pass the returned `session_id` to any endpoint that takes
        a project (session) ID. This is not supported on a BYOC data plane yet, and is a
        501 there.

        Args:
          kind: The kind of address.

          id: The Agent's user-assigned id for AGENT, or the experiment's id for EXPERIMENT.
              Not set for EVALUATOR.

          environment: The Agent environment. Only set for AGENT.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/api/v1/sessions/resolutions",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "kind": kind,
                        "id": id,
                        "environment": environment,
                    },
                    session_resolve_params.SessionResolveParams,
                ),
            ),
            cast_to=SessionResolveResponse,
        )


class SessionsResourceWithRawResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self._sessions = sessions

        self.resolve = to_raw_response_wrapper(
            sessions.resolve,
        )


class AsyncSessionsResourceWithRawResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self._sessions = sessions

        self.resolve = async_to_raw_response_wrapper(
            sessions.resolve,
        )


class SessionsResourceWithStreamingResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self._sessions = sessions

        self.resolve = to_streamed_response_wrapper(
            sessions.resolve,
        )


class AsyncSessionsResourceWithStreamingResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self._sessions = sessions

        self.resolve = async_to_streamed_response_wrapper(
            sessions.resolve,
        )
