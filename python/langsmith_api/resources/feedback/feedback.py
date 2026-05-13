# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Union, Optional
from datetime import datetime

import httpx

from .tokens import (
    TokensResource,
    AsyncTokensResource,
    TokensResourceWithRawResponse,
    AsyncTokensResourceWithRawResponse,
    TokensResourceWithStreamingResponse,
    AsyncTokensResourceWithStreamingResponse,
)
from ...types import (
    FeedbackLevel,
    feedback_list_params,
    feedback_create_params,
    feedback_update_params,
    feedback_retrieve_params,
)
from .configs import (
    ConfigsResource,
    AsyncConfigsResource,
    ConfigsResourceWithRawResponse,
    AsyncConfigsResourceWithRawResponse,
    ConfigsResourceWithStreamingResponse,
    AsyncConfigsResourceWithStreamingResponse,
)
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import SyncOffsetPaginationTopLevelArray, AsyncOffsetPaginationTopLevelArray
from ..._base_client import AsyncPaginator, make_request_options
from ...types.source_type import SourceType
from ...types.feedback_level import FeedbackLevel
from ...types.feedback_schema import FeedbackSchema

__all__ = ["FeedbackResource", "AsyncFeedbackResource"]


class FeedbackResource(SyncAPIResource):
    @cached_property
    def tokens(self) -> TokensResource:
        return TokensResource(self._client)

    @cached_property
    def configs(self) -> ConfigsResource:
        return ConfigsResource(self._client)

    @cached_property
    def with_raw_response(self) -> FeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return FeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> FeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return FeedbackResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        key: str,
        id: str | Omit = omit,
        comment: Optional[str] | Omit = omit,
        comparative_experiment_id: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        feedback_config: Optional[feedback_create_params.FeedbackConfig] | Omit = omit,
        feedback_group_id: Optional[str] | Omit = omit,
        feedback_source: Optional[feedback_create_params.FeedbackSource] | Omit = omit,
        modified_at: Union[str, datetime] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        session_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        value: Union[float, bool, str, Dict[str, object], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Create a new feedback.

        Args:
          feedback_source: Feedback from the LangChainPlus App.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/feedback",
            body=maybe_transform(
                {
                    "key": key,
                    "id": id,
                    "comment": comment,
                    "comparative_experiment_id": comparative_experiment_id,
                    "correction": correction,
                    "created_at": created_at,
                    "error": error,
                    "feedback_config": feedback_config,
                    "feedback_group_id": feedback_group_id,
                    "feedback_source": feedback_source,
                    "modified_at": modified_at,
                    "run_id": run_id,
                    "score": score,
                    "session_id": session_id,
                    "start_time": start_time,
                    "trace_id": trace_id,
                    "value": value,
                },
                feedback_create_params.FeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackSchema,
        )

    def retrieve(
        self,
        feedback_id: str,
        *,
        include_user_names: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Get a specific feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return self._get(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"include_user_names": include_user_names}, feedback_retrieve_params.FeedbackRetrieveParams
                ),
            ),
            cast_to=FeedbackSchema,
        )

    def update(
        self,
        feedback_id: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        feedback_config: Optional[feedback_update_params.FeedbackConfig] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, Dict[str, object], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Replace an existing feedback entry with a new, modified entry.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return self._patch(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            body=maybe_transform(
                {
                    "comment": comment,
                    "correction": correction,
                    "feedback_config": feedback_config,
                    "score": score,
                    "value": value,
                },
                feedback_update_params.FeedbackUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackSchema,
        )

    def list(
        self,
        *,
        comparative_experiment_id: Optional[str] | Omit = omit,
        has_comment: Optional[bool] | Omit = omit,
        has_score: Optional[bool] | Omit = omit,
        include_user_names: Optional[bool] | Omit = omit,
        key: Optional[SequenceNotStr[str]] | Omit = omit,
        level: Optional[FeedbackLevel] | Omit = omit,
        limit: int | Omit = omit,
        max_created_at: Union[str, datetime, None] | Omit = omit,
        min_created_at: Union[str, datetime, None] | Omit = omit,
        offset: int | Omit = omit,
        run: Union[SequenceNotStr[str], str, None] | Omit = omit,
        session: Union[SequenceNotStr[str], str, None] | Omit = omit,
        source: Optional[List[SourceType]] | Omit = omit,
        user: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[FeedbackSchema]:
        """
        List all Feedback by query params.

        Args:
          level: Enum for feedback levels.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/feedback",
            page=SyncOffsetPaginationTopLevelArray[FeedbackSchema],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "comparative_experiment_id": comparative_experiment_id,
                        "has_comment": has_comment,
                        "has_score": has_score,
                        "include_user_names": include_user_names,
                        "key": key,
                        "level": level,
                        "limit": limit,
                        "max_created_at": max_created_at,
                        "min_created_at": min_created_at,
                        "offset": offset,
                        "run": run,
                        "session": session,
                        "source": source,
                        "user": user,
                    },
                    feedback_list_params.FeedbackListParams,
                ),
            ),
            model=FeedbackSchema,
        )

    def delete(
        self,
        feedback_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return self._delete(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncFeedbackResource(AsyncAPIResource):
    @cached_property
    def tokens(self) -> AsyncTokensResource:
        return AsyncTokensResource(self._client)

    @cached_property
    def configs(self) -> AsyncConfigsResource:
        return AsyncConfigsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncFeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncFeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncFeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncFeedbackResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        key: str,
        id: str | Omit = omit,
        comment: Optional[str] | Omit = omit,
        comparative_experiment_id: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        error: Optional[bool] | Omit = omit,
        feedback_config: Optional[feedback_create_params.FeedbackConfig] | Omit = omit,
        feedback_group_id: Optional[str] | Omit = omit,
        feedback_source: Optional[feedback_create_params.FeedbackSource] | Omit = omit,
        modified_at: Union[str, datetime] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        session_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        value: Union[float, bool, str, Dict[str, object], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Create a new feedback.

        Args:
          feedback_source: Feedback from the LangChainPlus App.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/feedback",
            body=await async_maybe_transform(
                {
                    "key": key,
                    "id": id,
                    "comment": comment,
                    "comparative_experiment_id": comparative_experiment_id,
                    "correction": correction,
                    "created_at": created_at,
                    "error": error,
                    "feedback_config": feedback_config,
                    "feedback_group_id": feedback_group_id,
                    "feedback_source": feedback_source,
                    "modified_at": modified_at,
                    "run_id": run_id,
                    "score": score,
                    "session_id": session_id,
                    "start_time": start_time,
                    "trace_id": trace_id,
                    "value": value,
                },
                feedback_create_params.FeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackSchema,
        )

    async def retrieve(
        self,
        feedback_id: str,
        *,
        include_user_names: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Get a specific feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return await self._get(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"include_user_names": include_user_names}, feedback_retrieve_params.FeedbackRetrieveParams
                ),
            ),
            cast_to=FeedbackSchema,
        )

    async def update(
        self,
        feedback_id: str,
        *,
        comment: Optional[str] | Omit = omit,
        correction: Union[Dict[str, object], str, None] | Omit = omit,
        feedback_config: Optional[feedback_update_params.FeedbackConfig] | Omit = omit,
        score: Union[float, bool, None] | Omit = omit,
        value: Union[float, bool, str, Dict[str, object], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackSchema:
        """
        Replace an existing feedback entry with a new, modified entry.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return await self._patch(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            body=await async_maybe_transform(
                {
                    "comment": comment,
                    "correction": correction,
                    "feedback_config": feedback_config,
                    "score": score,
                    "value": value,
                },
                feedback_update_params.FeedbackUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackSchema,
        )

    def list(
        self,
        *,
        comparative_experiment_id: Optional[str] | Omit = omit,
        has_comment: Optional[bool] | Omit = omit,
        has_score: Optional[bool] | Omit = omit,
        include_user_names: Optional[bool] | Omit = omit,
        key: Optional[SequenceNotStr[str]] | Omit = omit,
        level: Optional[FeedbackLevel] | Omit = omit,
        limit: int | Omit = omit,
        max_created_at: Union[str, datetime, None] | Omit = omit,
        min_created_at: Union[str, datetime, None] | Omit = omit,
        offset: int | Omit = omit,
        run: Union[SequenceNotStr[str], str, None] | Omit = omit,
        session: Union[SequenceNotStr[str], str, None] | Omit = omit,
        source: Optional[List[SourceType]] | Omit = omit,
        user: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[FeedbackSchema, AsyncOffsetPaginationTopLevelArray[FeedbackSchema]]:
        """
        List all Feedback by query params.

        Args:
          level: Enum for feedback levels.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/feedback",
            page=AsyncOffsetPaginationTopLevelArray[FeedbackSchema],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "comparative_experiment_id": comparative_experiment_id,
                        "has_comment": has_comment,
                        "has_score": has_score,
                        "include_user_names": include_user_names,
                        "key": key,
                        "level": level,
                        "limit": limit,
                        "max_created_at": max_created_at,
                        "min_created_at": min_created_at,
                        "offset": offset,
                        "run": run,
                        "session": session,
                        "source": source,
                        "user": user,
                    },
                    feedback_list_params.FeedbackListParams,
                ),
            ),
            model=FeedbackSchema,
        )

    async def delete(
        self,
        feedback_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not feedback_id:
            raise ValueError(f"Expected a non-empty value for `feedback_id` but received {feedback_id!r}")
        return await self._delete(
            path_template("/api/v1/feedback/{feedback_id}", feedback_id=feedback_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class FeedbackResourceWithRawResponse:
    def __init__(self, feedback: FeedbackResource) -> None:
        self._feedback = feedback

        self.create = to_raw_response_wrapper(
            feedback.create,
        )
        self.retrieve = to_raw_response_wrapper(
            feedback.retrieve,
        )
        self.update = to_raw_response_wrapper(
            feedback.update,
        )
        self.list = to_raw_response_wrapper(
            feedback.list,
        )
        self.delete = to_raw_response_wrapper(
            feedback.delete,
        )

    @cached_property
    def tokens(self) -> TokensResourceWithRawResponse:
        return TokensResourceWithRawResponse(self._feedback.tokens)

    @cached_property
    def configs(self) -> ConfigsResourceWithRawResponse:
        return ConfigsResourceWithRawResponse(self._feedback.configs)


class AsyncFeedbackResourceWithRawResponse:
    def __init__(self, feedback: AsyncFeedbackResource) -> None:
        self._feedback = feedback

        self.create = async_to_raw_response_wrapper(
            feedback.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            feedback.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            feedback.update,
        )
        self.list = async_to_raw_response_wrapper(
            feedback.list,
        )
        self.delete = async_to_raw_response_wrapper(
            feedback.delete,
        )

    @cached_property
    def tokens(self) -> AsyncTokensResourceWithRawResponse:
        return AsyncTokensResourceWithRawResponse(self._feedback.tokens)

    @cached_property
    def configs(self) -> AsyncConfigsResourceWithRawResponse:
        return AsyncConfigsResourceWithRawResponse(self._feedback.configs)


class FeedbackResourceWithStreamingResponse:
    def __init__(self, feedback: FeedbackResource) -> None:
        self._feedback = feedback

        self.create = to_streamed_response_wrapper(
            feedback.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            feedback.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            feedback.update,
        )
        self.list = to_streamed_response_wrapper(
            feedback.list,
        )
        self.delete = to_streamed_response_wrapper(
            feedback.delete,
        )

    @cached_property
    def tokens(self) -> TokensResourceWithStreamingResponse:
        return TokensResourceWithStreamingResponse(self._feedback.tokens)

    @cached_property
    def configs(self) -> ConfigsResourceWithStreamingResponse:
        return ConfigsResourceWithStreamingResponse(self._feedback.configs)


class AsyncFeedbackResourceWithStreamingResponse:
    def __init__(self, feedback: AsyncFeedbackResource) -> None:
        self._feedback = feedback

        self.create = async_to_streamed_response_wrapper(
            feedback.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            feedback.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            feedback.update,
        )
        self.list = async_to_streamed_response_wrapper(
            feedback.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            feedback.delete,
        )

    @cached_property
    def tokens(self) -> AsyncTokensResourceWithStreamingResponse:
        return AsyncTokensResourceWithStreamingResponse(self._feedback.tokens)

    @cached_property
    def configs(self) -> AsyncConfigsResourceWithStreamingResponse:
        return AsyncConfigsResourceWithStreamingResponse(self._feedback.configs)
