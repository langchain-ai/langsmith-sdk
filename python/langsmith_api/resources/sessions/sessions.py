# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Literal

import httpx

from ...types import (
    SessionSortableColumns,
    session_list_params,
    session_create_params,
    session_update_params,
    session_retrieve_params,
    session_dashboard_params,
)
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from .insights import (
    InsightsResource,
    AsyncInsightsResource,
    InsightsResourceWithRawResponse,
    AsyncInsightsResourceWithRawResponse,
    InsightsResourceWithStreamingResponse,
    AsyncInsightsResourceWithStreamingResponse,
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
from ...types.tracer_session import TracerSession
from ...types.custom_charts_section import CustomChartsSection
from ...types.timedelta_input_param import TimedeltaInputParam
from ...types.run_stats_group_by_param import RunStatsGroupByParam
from ...types.session_sortable_columns import SessionSortableColumns
from ...types.tracer_session_without_virtual_fields import TracerSessionWithoutVirtualFields

__all__ = ["SessionsResource", "AsyncSessionsResource"]


class SessionsResource(SyncAPIResource):
    @cached_property
    def insights(self) -> InsightsResource:
        return InsightsResource(self._client)

    @cached_property
    def with_raw_response(self) -> SessionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return SessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SessionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return SessionsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        upsert: bool | Omit = omit,
        id: Optional[str] | Omit = omit,
        default_dataset_id: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        name: str | Omit = omit,
        reference_dataset_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime] | Omit = omit,
        trace_tier: Optional[Literal["longlived", "shortlived"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSessionWithoutVirtualFields:
        """
        Create a new session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/sessions",
            body=maybe_transform(
                {
                    "id": id,
                    "default_dataset_id": default_dataset_id,
                    "description": description,
                    "end_time": end_time,
                    "extra": extra,
                    "name": name,
                    "reference_dataset_id": reference_dataset_id,
                    "start_time": start_time,
                    "trace_tier": trace_tier,
                },
                session_create_params.SessionCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"upsert": upsert}, session_create_params.SessionCreateParams),
            ),
            cast_to=TracerSessionWithoutVirtualFields,
        )

    def retrieve(
        self,
        session_id: str,
        *,
        include_stats: bool | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSession:
        """
        Get a specific session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._get(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "include_stats": include_stats,
                        "stats_start_time": stats_start_time,
                    },
                    session_retrieve_params.SessionRetrieveParams,
                ),
            ),
            cast_to=TracerSession,
        )

    def update(
        self,
        session_id: str,
        *,
        default_dataset_id: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        name: Optional[str] | Omit = omit,
        trace_tier: Optional[Literal["longlived", "shortlived"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSessionWithoutVirtualFields:
        """
        Update a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return self._patch(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            body=maybe_transform(
                {
                    "default_dataset_id": default_dataset_id,
                    "description": description,
                    "end_time": end_time,
                    "extra": extra,
                    "name": name,
                    "trace_tier": trace_tier,
                },
                session_update_params.SessionUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TracerSessionWithoutVirtualFields,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        dataset_version: Optional[str] | Omit = omit,
        facets: bool | Omit = omit,
        filter: Optional[str] | Omit = omit,
        include_stats: bool | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        reference_dataset: Optional[SequenceNotStr[str]] | Omit = omit,
        reference_free: Optional[bool] | Omit = omit,
        sort_by: SessionSortableColumns | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        sort_by_feedback_key: Optional[str] | Omit = omit,
        stats_filter: Optional[str] | Omit = omit,
        stats_select: Optional[SequenceNotStr[str]] | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        use_approx_stats: bool | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[TracerSession]:
        """
        Get all sessions.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            "/api/v1/sessions",
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
                        "filter": filter,
                        "include_stats": include_stats,
                        "limit": limit,
                        "metadata": metadata,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "reference_dataset": reference_dataset,
                        "reference_free": reference_free,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "sort_by_feedback_key": sort_by_feedback_key,
                        "stats_filter": stats_filter,
                        "stats_select": stats_select,
                        "stats_start_time": stats_start_time,
                        "tag_value_id": tag_value_id,
                        "use_approx_stats": use_approx_stats,
                    },
                    session_list_params.SessionListParams,
                ),
            ),
            model=TracerSession,
        )

    def delete(
        self,
        session_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return self._delete(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def dashboard(
        self,
        session_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        group_by: Optional[RunStatsGroupByParam] | Omit = omit,
        omit_data: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        stride: TimedeltaInputParam | Omit = omit,
        timezone: str | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CustomChartsSection:
        """
        Get a prebuilt dashboard for a tracing project.

        Args:
          group_by: Group by param for run stats.

          stride: Timedelta input.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._post(
            path_template("/api/v1/sessions/{session_id}/dashboard", session_id=session_id),
            body=maybe_transform(
                {
                    "end_time": end_time,
                    "group_by": group_by,
                    "omit_data": omit_data,
                    "start_time": start_time,
                    "stride": stride,
                    "timezone": timezone,
                },
                session_dashboard_params.SessionDashboardParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CustomChartsSection,
        )


class AsyncSessionsResource(AsyncAPIResource):
    @cached_property
    def insights(self) -> AsyncInsightsResource:
        return AsyncInsightsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncSessionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSessionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSessionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncSessionsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        upsert: bool | Omit = omit,
        id: Optional[str] | Omit = omit,
        default_dataset_id: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        name: str | Omit = omit,
        reference_dataset_id: Optional[str] | Omit = omit,
        start_time: Union[str, datetime] | Omit = omit,
        trace_tier: Optional[Literal["longlived", "shortlived"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSessionWithoutVirtualFields:
        """
        Create a new session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/sessions",
            body=await async_maybe_transform(
                {
                    "id": id,
                    "default_dataset_id": default_dataset_id,
                    "description": description,
                    "end_time": end_time,
                    "extra": extra,
                    "name": name,
                    "reference_dataset_id": reference_dataset_id,
                    "start_time": start_time,
                    "trace_tier": trace_tier,
                },
                session_create_params.SessionCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"upsert": upsert}, session_create_params.SessionCreateParams),
            ),
            cast_to=TracerSessionWithoutVirtualFields,
        )

    async def retrieve(
        self,
        session_id: str,
        *,
        include_stats: bool | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSession:
        """
        Get a specific session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return await self._get(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "include_stats": include_stats,
                        "stats_start_time": stats_start_time,
                    },
                    session_retrieve_params.SessionRetrieveParams,
                ),
            ),
            cast_to=TracerSession,
        )

    async def update(
        self,
        session_id: str,
        *,
        default_dataset_id: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        name: Optional[str] | Omit = omit,
        trace_tier: Optional[Literal["longlived", "shortlived"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TracerSessionWithoutVirtualFields:
        """
        Update a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return await self._patch(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            body=await async_maybe_transform(
                {
                    "default_dataset_id": default_dataset_id,
                    "description": description,
                    "end_time": end_time,
                    "extra": extra,
                    "name": name,
                    "trace_tier": trace_tier,
                },
                session_update_params.SessionUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TracerSessionWithoutVirtualFields,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        dataset_version: Optional[str] | Omit = omit,
        facets: bool | Omit = omit,
        filter: Optional[str] | Omit = omit,
        include_stats: bool | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        reference_dataset: Optional[SequenceNotStr[str]] | Omit = omit,
        reference_free: Optional[bool] | Omit = omit,
        sort_by: SessionSortableColumns | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        sort_by_feedback_key: Optional[str] | Omit = omit,
        stats_filter: Optional[str] | Omit = omit,
        stats_select: Optional[SequenceNotStr[str]] | Omit = omit,
        stats_start_time: Union[str, datetime, None] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        use_approx_stats: bool | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[TracerSession, AsyncOffsetPaginationTopLevelArray[TracerSession]]:
        """
        Get all sessions.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._get_api_list(
            "/api/v1/sessions",
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
                        "filter": filter,
                        "include_stats": include_stats,
                        "limit": limit,
                        "metadata": metadata,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "reference_dataset": reference_dataset,
                        "reference_free": reference_free,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "sort_by_feedback_key": sort_by_feedback_key,
                        "stats_filter": stats_filter,
                        "stats_select": stats_select,
                        "stats_start_time": stats_start_time,
                        "tag_value_id": tag_value_id,
                        "use_approx_stats": use_approx_stats,
                    },
                    session_list_params.SessionListParams,
                ),
            ),
            model=TracerSession,
        )

    async def delete(
        self,
        session_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return await self._delete(
            path_template("/api/v1/sessions/{session_id}", session_id=session_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def dashboard(
        self,
        session_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        group_by: Optional[RunStatsGroupByParam] | Omit = omit,
        omit_data: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        stride: TimedeltaInputParam | Omit = omit,
        timezone: str | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CustomChartsSection:
        """
        Get a prebuilt dashboard for a tracing project.

        Args:
          group_by: Group by param for run stats.

          stride: Timedelta input.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return await self._post(
            path_template("/api/v1/sessions/{session_id}/dashboard", session_id=session_id),
            body=await async_maybe_transform(
                {
                    "end_time": end_time,
                    "group_by": group_by,
                    "omit_data": omit_data,
                    "start_time": start_time,
                    "stride": stride,
                    "timezone": timezone,
                },
                session_dashboard_params.SessionDashboardParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CustomChartsSection,
        )


class SessionsResourceWithRawResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self._sessions = sessions

        self.create = to_raw_response_wrapper(
            sessions.create,
        )
        self.retrieve = to_raw_response_wrapper(
            sessions.retrieve,
        )
        self.update = to_raw_response_wrapper(
            sessions.update,
        )
        self.list = to_raw_response_wrapper(
            sessions.list,
        )
        self.delete = to_raw_response_wrapper(
            sessions.delete,
        )
        self.dashboard = to_raw_response_wrapper(
            sessions.dashboard,
        )

    @cached_property
    def insights(self) -> InsightsResourceWithRawResponse:
        return InsightsResourceWithRawResponse(self._sessions.insights)


class AsyncSessionsResourceWithRawResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self._sessions = sessions

        self.create = async_to_raw_response_wrapper(
            sessions.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            sessions.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            sessions.update,
        )
        self.list = async_to_raw_response_wrapper(
            sessions.list,
        )
        self.delete = async_to_raw_response_wrapper(
            sessions.delete,
        )
        self.dashboard = async_to_raw_response_wrapper(
            sessions.dashboard,
        )

    @cached_property
    def insights(self) -> AsyncInsightsResourceWithRawResponse:
        return AsyncInsightsResourceWithRawResponse(self._sessions.insights)


class SessionsResourceWithStreamingResponse:
    def __init__(self, sessions: SessionsResource) -> None:
        self._sessions = sessions

        self.create = to_streamed_response_wrapper(
            sessions.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            sessions.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            sessions.update,
        )
        self.list = to_streamed_response_wrapper(
            sessions.list,
        )
        self.delete = to_streamed_response_wrapper(
            sessions.delete,
        )
        self.dashboard = to_streamed_response_wrapper(
            sessions.dashboard,
        )

    @cached_property
    def insights(self) -> InsightsResourceWithStreamingResponse:
        return InsightsResourceWithStreamingResponse(self._sessions.insights)


class AsyncSessionsResourceWithStreamingResponse:
    def __init__(self, sessions: AsyncSessionsResource) -> None:
        self._sessions = sessions

        self.create = async_to_streamed_response_wrapper(
            sessions.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            sessions.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            sessions.update,
        )
        self.list = async_to_streamed_response_wrapper(
            sessions.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            sessions.delete,
        )
        self.dashboard = async_to_streamed_response_wrapper(
            sessions.dashboard,
        )

    @cached_property
    def insights(self) -> AsyncInsightsResourceWithStreamingResponse:
        return AsyncInsightsResourceWithStreamingResponse(self._sessions.insights)
