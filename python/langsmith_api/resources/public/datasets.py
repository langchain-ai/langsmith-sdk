# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional

import httpx

from ...types import FeedbackLevel, SortByDatasetColumn, SessionSortableColumns
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
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
from ...types.public import (
    dataset_list_params,
    dataset_list_feedback_params,
    dataset_list_sessions_params,
    dataset_list_comparative_params,
    dataset_retrieve_sessions_bulk_params,
)
from ...types.datasets import SortByComparativeExperimentColumn
from ...types.source_type import SourceType
from ...types.feedback_level import FeedbackLevel
from ...types.tracer_session import TracerSession
from ...types.feedback_schema import FeedbackSchema
from ...types.sort_by_dataset_column import SortByDatasetColumn
from ...types.session_sortable_columns import SessionSortableColumns
from ...types.public.dataset_list_response import DatasetListResponse
from ...types.public.dataset_list_comparative_response import DatasetListComparativeResponse
from ...types.datasets.sort_by_comparative_experiment_column import SortByComparativeExperimentColumn
from ...types.public.dataset_retrieve_sessions_bulk_response import DatasetRetrieveSessionsBulkResponse

__all__ = ["DatasetsResource", "AsyncDatasetsResource"]


class DatasetsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> DatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return DatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return DatasetsResourceWithStreamingResponse(self)

    def list(
        self,
        share_token: str,
        *,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByDatasetColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetListResponse:
        """
        Get dataset by ids or the shared dataset if not specifed.

        Args:
          sort_by: Enum for available dataset columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get(
            path_template("/api/v1/public/{share_token}/datasets", share_token=share_token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                    },
                    dataset_list_params.DatasetListParams,
                ),
            ),
            cast_to=DatasetListResponse,
        )

    def list_comparative(
        self,
        share_token: str,
        *,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByComparativeExperimentColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[DatasetListComparativeResponse]:
        """
        Get all comparative experiments for a given dataset.

        Args:
          sort_by: Enum for available comparative experiment columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/datasets/comparative", share_token=share_token),
            page=SyncOffsetPaginationTopLevelArray[DatasetListComparativeResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                    },
                    dataset_list_comparative_params.DatasetListComparativeParams,
                ),
            ),
            model=DatasetListComparativeResponse,
        )

    def list_feedback(
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
        Get feedback for runs in projects run over a dataset that has been shared.

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
            path_template("/api/v1/public/{share_token}/datasets/feedback", share_token=share_token),
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
                    dataset_list_feedback_params.DatasetListFeedbackParams,
                ),
            ),
            model=FeedbackSchema,
        )

    def list_sessions(
        self,
        share_token: str,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        dataset_version: Optional[str] | Omit = omit,
        facets: bool | Omit = omit,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SessionSortableColumns | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        sort_by_feedback_key: Optional[str] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[TracerSession]:
        """
        Get projects run on a dataset that has been shared.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/datasets/sessions", share_token=share_token),
            page=SyncOffsetPaginationTopLevelArray[TracerSession],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "dataset_version": dataset_version,
                        "facets": facets,
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "sort_by_feedback_key": sort_by_feedback_key,
                    },
                    dataset_list_sessions_params.DatasetListSessionsParams,
                ),
            ),
            model=TracerSession,
        )

    def retrieve_sessions_bulk(
        self,
        *,
        share_tokens: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetRetrieveSessionsBulkResponse:
        """
        Get sessions from multiple datasets using share tokens.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/api/v1/public/datasets/sessions-bulk",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"share_tokens": share_tokens},
                    dataset_retrieve_sessions_bulk_params.DatasetRetrieveSessionsBulkParams,
                ),
            ),
            cast_to=DatasetRetrieveSessionsBulkResponse,
        )


class AsyncDatasetsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncDatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncDatasetsResourceWithStreamingResponse(self)

    async def list(
        self,
        share_token: str,
        *,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByDatasetColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetListResponse:
        """
        Get dataset by ids or the shared dataset if not specifed.

        Args:
          sort_by: Enum for available dataset columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return await self._get(
            path_template("/api/v1/public/{share_token}/datasets", share_token=share_token),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                    },
                    dataset_list_params.DatasetListParams,
                ),
            ),
            cast_to=DatasetListResponse,
        )

    def list_comparative(
        self,
        share_token: str,
        *,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByComparativeExperimentColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[
        DatasetListComparativeResponse, AsyncOffsetPaginationTopLevelArray[DatasetListComparativeResponse]
    ]:
        """
        Get all comparative experiments for a given dataset.

        Args:
          sort_by: Enum for available comparative experiment columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/datasets/comparative", share_token=share_token),
            page=AsyncOffsetPaginationTopLevelArray[DatasetListComparativeResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                    },
                    dataset_list_comparative_params.DatasetListComparativeParams,
                ),
            ),
            model=DatasetListComparativeResponse,
        )

    def list_feedback(
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
        Get feedback for runs in projects run over a dataset that has been shared.

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
            path_template("/api/v1/public/{share_token}/datasets/feedback", share_token=share_token),
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
                    dataset_list_feedback_params.DatasetListFeedbackParams,
                ),
            ),
            model=FeedbackSchema,
        )

    def list_sessions(
        self,
        share_token: str,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        dataset_version: Optional[str] | Omit = omit,
        facets: bool | Omit = omit,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SessionSortableColumns | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        sort_by_feedback_key: Optional[str] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[TracerSession, AsyncOffsetPaginationTopLevelArray[TracerSession]]:
        """
        Get projects run on a dataset that has been shared.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            path_template("/api/v1/public/{share_token}/datasets/sessions", share_token=share_token),
            page=AsyncOffsetPaginationTopLevelArray[TracerSession],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "dataset_version": dataset_version,
                        "facets": facets,
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "sort_by_feedback_key": sort_by_feedback_key,
                    },
                    dataset_list_sessions_params.DatasetListSessionsParams,
                ),
            ),
            model=TracerSession,
        )

    async def retrieve_sessions_bulk(
        self,
        *,
        share_tokens: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetRetrieveSessionsBulkResponse:
        """
        Get sessions from multiple datasets using share tokens.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/api/v1/public/datasets/sessions-bulk",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"share_tokens": share_tokens},
                    dataset_retrieve_sessions_bulk_params.DatasetRetrieveSessionsBulkParams,
                ),
            ),
            cast_to=DatasetRetrieveSessionsBulkResponse,
        )


class DatasetsResourceWithRawResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

        self.list = to_raw_response_wrapper(
            datasets.list,
        )
        self.list_comparative = to_raw_response_wrapper(
            datasets.list_comparative,
        )
        self.list_feedback = to_raw_response_wrapper(
            datasets.list_feedback,
        )
        self.list_sessions = to_raw_response_wrapper(
            datasets.list_sessions,
        )
        self.retrieve_sessions_bulk = to_raw_response_wrapper(
            datasets.retrieve_sessions_bulk,
        )


class AsyncDatasetsResourceWithRawResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

        self.list = async_to_raw_response_wrapper(
            datasets.list,
        )
        self.list_comparative = async_to_raw_response_wrapper(
            datasets.list_comparative,
        )
        self.list_feedback = async_to_raw_response_wrapper(
            datasets.list_feedback,
        )
        self.list_sessions = async_to_raw_response_wrapper(
            datasets.list_sessions,
        )
        self.retrieve_sessions_bulk = async_to_raw_response_wrapper(
            datasets.retrieve_sessions_bulk,
        )


class DatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

        self.list = to_streamed_response_wrapper(
            datasets.list,
        )
        self.list_comparative = to_streamed_response_wrapper(
            datasets.list_comparative,
        )
        self.list_feedback = to_streamed_response_wrapper(
            datasets.list_feedback,
        )
        self.list_sessions = to_streamed_response_wrapper(
            datasets.list_sessions,
        )
        self.retrieve_sessions_bulk = to_streamed_response_wrapper(
            datasets.retrieve_sessions_bulk,
        )


class AsyncDatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

        self.list = async_to_streamed_response_wrapper(
            datasets.list,
        )
        self.list_comparative = async_to_streamed_response_wrapper(
            datasets.list_comparative,
        )
        self.list_feedback = async_to_streamed_response_wrapper(
            datasets.list_feedback,
        )
        self.list_sessions = async_to_streamed_response_wrapper(
            datasets.list_sessions,
        )
        self.retrieve_sessions_bulk = async_to_streamed_response_wrapper(
            datasets.retrieve_sessions_bulk,
        )
