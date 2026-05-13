# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Any, Dict, Union, Iterable, Optional, cast
from datetime import datetime
from typing_extensions import overload

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import path_template, required_args, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.feedback import token_list_params, token_create_params, token_update_params, token_retrieve_params
from ...types.timedelta_input_param import TimedeltaInputParam
from ...types.feedback.token_list_response import TokenListResponse
from ...types.feedback.token_create_response import TokenCreateResponse
from ...types.feedback.feedback_ingest_token_create_schema_param import FeedbackIngestTokenCreateSchemaParam

__all__ = ["TokensResource", "AsyncTokensResource"]


class TokensResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TokensResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return TokensResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TokensResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return TokensResourceWithStreamingResponse(self)

    @overload
    def create(
        self,
        *,
        feedback_key: str,
        run_id: str,
        expires_at: Union[str, datetime, None] | Omit = omit,
        expires_in: Optional[TimedeltaInputParam] | Omit = omit,
        feedback_config: Optional[token_create_params.FeedbackIngestTokenCreateSchemaFeedbackConfig] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        """
        Create a new feedback ingest token.

        Args:
          expires_in: Timedelta input.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    def create(
        self,
        *,
        body: Iterable[FeedbackIngestTokenCreateSchemaParam],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        """
        Create a new feedback ingest token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @required_args(["feedback_key", "run_id"], ["body"])
    def create(
        self,
        *,
        feedback_key: str | Omit = omit,
        run_id: str | Omit = omit,
        expires_at: Union[str, datetime, None] | Omit = omit,
        expires_in: Optional[TimedeltaInputParam] | Omit = omit,
        feedback_config: Optional[token_create_params.FeedbackIngestTokenCreateSchemaFeedbackConfig] | Omit = omit,
        body: Iterable[FeedbackIngestTokenCreateSchemaParam] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        return cast(
            TokenCreateResponse,
            self._post(
                "/api/v1/feedback/tokens",
                body=maybe_transform(
                    {
                        "feedback_key": feedback_key,
                        "run_id": run_id,
                        "expires_at": expires_at,
                        "expires_in": expires_in,
                        "feedback_config": feedback_config,
                        "body": body,
                    },
                    token_create_params.TokenCreateParams,
                ),
                options=make_request_options(
                    extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
                ),
                cast_to=cast(
                    Any, TokenCreateResponse
                ),  # Union types cannot be passed in as arguments in the type system
            ),
        )

    def retrieve(
        self,
        token: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Optional[str] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create a new feedback with a token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not token:
            raise ValueError(f"Expected a non-empty value for `token` but received {token!r}")
        return self._get(
            path_template("/api/v1/feedback/tokens/{token}", token=token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "comment": comment,
                        "correction": correction,
                        "score": score,
                        "value": value,
                    },
                    token_retrieve_params.TokenRetrieveParams,
                ),
            ),
            cast_to=object,
        )

    def update(
        self,
        token: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create a new feedback with a token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not token:
            raise ValueError(f"Expected a non-empty value for `token` but received {token!r}")
        return self._post(
            path_template("/api/v1/feedback/tokens/{token}", token=token),
            body=maybe_transform(
                {
                    "comment": comment,
                    "correction": correction,
                    "metadata": metadata,
                    "score": score,
                    "value": value,
                },
                token_update_params.TokenUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def list(
        self,
        *,
        run_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenListResponse:
        """
        List all feedback ingest tokens for a run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/api/v1/feedback/tokens",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"run_id": run_id}, token_list_params.TokenListParams),
            ),
            cast_to=TokenListResponse,
        )


class AsyncTokensResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTokensResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTokensResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTokensResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncTokensResourceWithStreamingResponse(self)

    @overload
    async def create(
        self,
        *,
        feedback_key: str,
        run_id: str,
        expires_at: Union[str, datetime, None] | Omit = omit,
        expires_in: Optional[TimedeltaInputParam] | Omit = omit,
        feedback_config: Optional[token_create_params.FeedbackIngestTokenCreateSchemaFeedbackConfig] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        """
        Create a new feedback ingest token.

        Args:
          expires_in: Timedelta input.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    async def create(
        self,
        *,
        body: Iterable[FeedbackIngestTokenCreateSchemaParam],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        """
        Create a new feedback ingest token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @required_args(["feedback_key", "run_id"], ["body"])
    async def create(
        self,
        *,
        feedback_key: str | Omit = omit,
        run_id: str | Omit = omit,
        expires_at: Union[str, datetime, None] | Omit = omit,
        expires_in: Optional[TimedeltaInputParam] | Omit = omit,
        feedback_config: Optional[token_create_params.FeedbackIngestTokenCreateSchemaFeedbackConfig] | Omit = omit,
        body: Iterable[FeedbackIngestTokenCreateSchemaParam] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenCreateResponse:
        return cast(
            TokenCreateResponse,
            await self._post(
                "/api/v1/feedback/tokens",
                body=await async_maybe_transform(
                    {
                        "feedback_key": feedback_key,
                        "run_id": run_id,
                        "expires_at": expires_at,
                        "expires_in": expires_in,
                        "feedback_config": feedback_config,
                        "body": body,
                    },
                    token_create_params.TokenCreateParams,
                ),
                options=make_request_options(
                    extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
                ),
                cast_to=cast(
                    Any, TokenCreateResponse
                ),  # Union types cannot be passed in as arguments in the type system
            ),
        )

    async def retrieve(
        self,
        token: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Optional[str] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create a new feedback with a token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not token:
            raise ValueError(f"Expected a non-empty value for `token` but received {token!r}")
        return await self._get(
            path_template("/api/v1/feedback/tokens/{token}", token=token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "comment": comment,
                        "correction": correction,
                        "score": score,
                        "value": value,
                    },
                    token_retrieve_params.TokenRetrieveParams,
                ),
            ),
            cast_to=object,
        )

    async def update(
        self,
        token: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create a new feedback with a token.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not token:
            raise ValueError(f"Expected a non-empty value for `token` but received {token!r}")
        return await self._post(
            path_template("/api/v1/feedback/tokens/{token}", token=token),
            body=await async_maybe_transform(
                {
                    "comment": comment,
                    "correction": correction,
                    "metadata": metadata,
                    "score": score,
                    "value": value,
                },
                token_update_params.TokenUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def list(
        self,
        *,
        run_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TokenListResponse:
        """
        List all feedback ingest tokens for a run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/api/v1/feedback/tokens",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"run_id": run_id}, token_list_params.TokenListParams),
            ),
            cast_to=TokenListResponse,
        )


class TokensResourceWithRawResponse:
    def __init__(self, tokens: TokensResource) -> None:
        self._tokens = tokens

        self.create = to_raw_response_wrapper(
            tokens.create,
        )
        self.retrieve = to_raw_response_wrapper(
            tokens.retrieve,
        )
        self.update = to_raw_response_wrapper(
            tokens.update,
        )
        self.list = to_raw_response_wrapper(
            tokens.list,
        )


class AsyncTokensResourceWithRawResponse:
    def __init__(self, tokens: AsyncTokensResource) -> None:
        self._tokens = tokens

        self.create = async_to_raw_response_wrapper(
            tokens.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            tokens.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            tokens.update,
        )
        self.list = async_to_raw_response_wrapper(
            tokens.list,
        )


class TokensResourceWithStreamingResponse:
    def __init__(self, tokens: TokensResource) -> None:
        self._tokens = tokens

        self.create = to_streamed_response_wrapper(
            tokens.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            tokens.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            tokens.update,
        )
        self.list = to_streamed_response_wrapper(
            tokens.list,
        )


class AsyncTokensResourceWithStreamingResponse:
    def __init__(self, tokens: AsyncTokensResource) -> None:
        self._tokens = tokens

        self.create = async_to_streamed_response_wrapper(
            tokens.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            tokens.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            tokens.update,
        )
        self.list = async_to_streamed_response_wrapper(
            tokens.list,
        )
