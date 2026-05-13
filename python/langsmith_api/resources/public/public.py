# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional

import httpx

from .runs import (
    RunsResource,
    AsyncRunsResource,
    RunsResourceWithRawResponse,
    AsyncRunsResourceWithRawResponse,
    RunsResourceWithStreamingResponse,
    AsyncRunsResourceWithStreamingResponse,
)
from ...types import FeedbackLevel, public_retrieve_run_params, public_retrieve_feedbacks_params
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from .datasets import (
    DatasetsResource,
    AsyncDatasetsResource,
    DatasetsResourceWithRawResponse,
    AsyncDatasetsResourceWithRawResponse,
    DatasetsResourceWithStreamingResponse,
    AsyncDatasetsResourceWithStreamingResponse,
)
from .examples import (
    ExamplesResource,
    AsyncExamplesResource,
    ExamplesResourceWithRawResponse,
    AsyncExamplesResourceWithRawResponse,
    ExamplesResourceWithStreamingResponse,
    AsyncExamplesResourceWithStreamingResponse,
)
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
from ...types.public_retrieve_run_response import PublicRetrieveRunResponse

__all__ = ["PublicResource", "AsyncPublicResource"]


class PublicResource(SyncAPIResource):
    @cached_property
    def runs(self) -> RunsResource:
        return RunsResource(self._client)

    @cached_property
    def examples(self) -> ExamplesResource:
        return ExamplesResource(self._client)

    @cached_property
    def datasets(self) -> DatasetsResource:
        return DatasetsResource(self._client)

    @cached_property
    def with_raw_response(self) -> PublicResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return PublicResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> PublicResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return PublicResourceWithStreamingResponse(self)

    def retrieve_feedbacks(
        self,
        share_token: str,
        *,
        has_comment: Optional[bool] | Omit = omit,
        has_score: Optional[bool] | Omit = omit,
        key: Optional[SequenceNotStr[str]] | Omit = omit,
        level: Optional[FeedbackLevel] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        run: Optional[SequenceNotStr[str]] | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
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
        Read Shared Feedbacks

        Args:
          level: Enum for feedback levels.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/feedbacks", share_token=share_token),
            page=SyncOffsetPaginationTopLevelArray[FeedbackSchema],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "has_comment": has_comment,
                        "has_score": has_score,
                        "key": key,
                        "level": level,
                        "limit": limit,
                        "offset": offset,
                        "run": run,
                        "session": session,
                        "source": source,
                        "user": user,
                    },
                    public_retrieve_feedbacks_params.PublicRetrieveFeedbacksParams,
                ),
            ),
            model=FeedbackSchema,
        )

    def retrieve_run(
        self,
        share_token: str,
        *,
        exclude_s3_stored_attributes: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PublicRetrieveRunResponse:
        """
        Get the shared run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get(
            path_template("/api/v1/public/{share_token}/run", share_token=share_token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"exclude_s3_stored_attributes": exclude_s3_stored_attributes},
                    public_retrieve_run_params.PublicRetrieveRunParams,
                ),
            ),
            cast_to=PublicRetrieveRunResponse,
        )


class AsyncPublicResource(AsyncAPIResource):
    @cached_property
    def runs(self) -> AsyncRunsResource:
        return AsyncRunsResource(self._client)

    @cached_property
    def examples(self) -> AsyncExamplesResource:
        return AsyncExamplesResource(self._client)

    @cached_property
    def datasets(self) -> AsyncDatasetsResource:
        return AsyncDatasetsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncPublicResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncPublicResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncPublicResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncPublicResourceWithStreamingResponse(self)

    def retrieve_feedbacks(
        self,
        share_token: str,
        *,
        has_comment: Optional[bool] | Omit = omit,
        has_score: Optional[bool] | Omit = omit,
        key: Optional[SequenceNotStr[str]] | Omit = omit,
        level: Optional[FeedbackLevel] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        run: Optional[SequenceNotStr[str]] | Omit = omit,
        session: Optional[SequenceNotStr[str]] | Omit = omit,
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
        Read Shared Feedbacks

        Args:
          level: Enum for feedback levels.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/feedbacks", share_token=share_token),
            page=AsyncOffsetPaginationTopLevelArray[FeedbackSchema],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "has_comment": has_comment,
                        "has_score": has_score,
                        "key": key,
                        "level": level,
                        "limit": limit,
                        "offset": offset,
                        "run": run,
                        "session": session,
                        "source": source,
                        "user": user,
                    },
                    public_retrieve_feedbacks_params.PublicRetrieveFeedbacksParams,
                ),
            ),
            model=FeedbackSchema,
        )

    async def retrieve_run(
        self,
        share_token: str,
        *,
        exclude_s3_stored_attributes: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PublicRetrieveRunResponse:
        """
        Get the shared run.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return await self._get(
            path_template("/api/v1/public/{share_token}/run", share_token=share_token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"exclude_s3_stored_attributes": exclude_s3_stored_attributes},
                    public_retrieve_run_params.PublicRetrieveRunParams,
                ),
            ),
            cast_to=PublicRetrieveRunResponse,
        )


class PublicResourceWithRawResponse:
    def __init__(self, public: PublicResource) -> None:
        self._public = public

        self.retrieve_feedbacks = to_raw_response_wrapper(
            public.retrieve_feedbacks,
        )
        self.retrieve_run = to_raw_response_wrapper(
            public.retrieve_run,
        )

    @cached_property
    def runs(self) -> RunsResourceWithRawResponse:
        return RunsResourceWithRawResponse(self._public.runs)

    @cached_property
    def examples(self) -> ExamplesResourceWithRawResponse:
        return ExamplesResourceWithRawResponse(self._public.examples)

    @cached_property
    def datasets(self) -> DatasetsResourceWithRawResponse:
        return DatasetsResourceWithRawResponse(self._public.datasets)


class AsyncPublicResourceWithRawResponse:
    def __init__(self, public: AsyncPublicResource) -> None:
        self._public = public

        self.retrieve_feedbacks = async_to_raw_response_wrapper(
            public.retrieve_feedbacks,
        )
        self.retrieve_run = async_to_raw_response_wrapper(
            public.retrieve_run,
        )

    @cached_property
    def runs(self) -> AsyncRunsResourceWithRawResponse:
        return AsyncRunsResourceWithRawResponse(self._public.runs)

    @cached_property
    def examples(self) -> AsyncExamplesResourceWithRawResponse:
        return AsyncExamplesResourceWithRawResponse(self._public.examples)

    @cached_property
    def datasets(self) -> AsyncDatasetsResourceWithRawResponse:
        return AsyncDatasetsResourceWithRawResponse(self._public.datasets)


class PublicResourceWithStreamingResponse:
    def __init__(self, public: PublicResource) -> None:
        self._public = public

        self.retrieve_feedbacks = to_streamed_response_wrapper(
            public.retrieve_feedbacks,
        )
        self.retrieve_run = to_streamed_response_wrapper(
            public.retrieve_run,
        )

    @cached_property
    def runs(self) -> RunsResourceWithStreamingResponse:
        return RunsResourceWithStreamingResponse(self._public.runs)

    @cached_property
    def examples(self) -> ExamplesResourceWithStreamingResponse:
        return ExamplesResourceWithStreamingResponse(self._public.examples)

    @cached_property
    def datasets(self) -> DatasetsResourceWithStreamingResponse:
        return DatasetsResourceWithStreamingResponse(self._public.datasets)


class AsyncPublicResourceWithStreamingResponse:
    def __init__(self, public: AsyncPublicResource) -> None:
        self._public = public

        self.retrieve_feedbacks = async_to_streamed_response_wrapper(
            public.retrieve_feedbacks,
        )
        self.retrieve_run = async_to_streamed_response_wrapper(
            public.retrieve_run,
        )

    @cached_property
    def runs(self) -> AsyncRunsResourceWithStreamingResponse:
        return AsyncRunsResourceWithStreamingResponse(self._public.runs)

    @cached_property
    def examples(self) -> AsyncExamplesResourceWithStreamingResponse:
        return AsyncExamplesResourceWithStreamingResponse(self._public.examples)

    @cached_property
    def datasets(self) -> AsyncDatasetsResourceWithStreamingResponse:
        return AsyncDatasetsResourceWithStreamingResponse(self._public.datasets)
