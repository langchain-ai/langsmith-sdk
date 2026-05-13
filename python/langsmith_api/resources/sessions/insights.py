# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...pagination import SyncOffsetPaginationInsightsClusteringJobs, AsyncOffsetPaginationInsightsClusteringJobs
from ..._base_client import AsyncPaginator, make_request_options
from ...types.sessions import (
    insight_list_params,
    insight_create_params,
    insight_update_params,
    insight_retrieve_runs_params,
)
from ...types.sessions.insight_list_response import InsightListResponse
from ...types.sessions.insight_create_response import InsightCreateResponse
from ...types.sessions.insight_delete_response import InsightDeleteResponse
from ...types.sessions.insight_update_response import InsightUpdateResponse
from ...types.sessions.insight_retrieve_job_response import InsightRetrieveJobResponse
from ...types.sessions.insight_retrieve_runs_response import InsightRetrieveRunsResponse

__all__ = ["InsightsResource", "AsyncInsightsResource"]


class InsightsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> InsightsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return InsightsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> InsightsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return InsightsResourceWithStreamingResponse(self)

    def create(
        self,
        session_id: str,
        *,
        attribute_schemas: Optional[Dict[str, object]] | Omit = omit,
        cluster_model: Optional[str] | Omit = omit,
        config_id: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        hierarchy: Optional[Iterable[int]] | Omit = omit,
        is_scheduled: bool | Omit = omit,
        last_n_hours: Optional[int] | Omit = omit,
        model: Literal["openai", "anthropic"] | Omit = omit,
        name: Optional[str] | Omit = omit,
        partitions: Optional[Dict[str, str]] | Omit = omit,
        sample: Optional[float] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        summary_model: Optional[str] | Omit = omit,
        summary_prompt: Optional[str] | Omit = omit,
        user_context: Optional[Dict[str, str]] | Omit = omit,
        validate_model_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightCreateResponse:
        """
        Create an insights job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return self._post(
            path_template("/api/v1/sessions/{session_id}/insights", session_id=session_id),
            body=maybe_transform(
                {
                    "attribute_schemas": attribute_schemas,
                    "cluster_model": cluster_model,
                    "config_id": config_id,
                    "end_time": end_time,
                    "filter": filter,
                    "hierarchy": hierarchy,
                    "is_scheduled": is_scheduled,
                    "last_n_hours": last_n_hours,
                    "model": model,
                    "name": name,
                    "partitions": partitions,
                    "sample": sample,
                    "start_time": start_time,
                    "summary_model": summary_model,
                    "summary_prompt": summary_prompt,
                    "user_context": user_context,
                    "validate_model_secrets": validate_model_secrets,
                },
                insight_create_params.InsightCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightCreateResponse,
        )

    def update(
        self,
        job_id: str,
        *,
        session_id: str,
        name: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightUpdateResponse:
        """
        Update a session cluster job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return self._patch(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            body=maybe_transform({"name": name}, insight_update_params.InsightUpdateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightUpdateResponse,
        )

    def list(
        self,
        session_id: str,
        *,
        config_id: Optional[str] | Omit = omit,
        legacy: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationInsightsClusteringJobs[InsightListResponse]:
        """
        Get all clusters for a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return self._get_api_list(
            path_template("/api/v1/sessions/{session_id}/insights", session_id=session_id),
            page=SyncOffsetPaginationInsightsClusteringJobs[InsightListResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "config_id": config_id,
                        "legacy": legacy,
                        "limit": limit,
                        "offset": offset,
                    },
                    insight_list_params.InsightListParams,
                ),
            ),
            model=InsightListResponse,
        )

    def delete(
        self,
        job_id: str,
        *,
        session_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightDeleteResponse:
        """
        Delete a session cluster job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return self._delete(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightDeleteResponse,
        )

    def retrieve_job(
        self,
        job_id: str,
        *,
        session_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightRetrieveJobResponse:
        """
        Get a specific cluster job for a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return self._get(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightRetrieveJobResponse,
        )

    def retrieve_runs(
        self,
        job_id: str,
        *,
        session_id: str,
        attribute_sort_key: Optional[str] | Omit = omit,
        attribute_sort_order: Optional[Literal["asc", "desc"]] | Omit = omit,
        cluster_id: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightRetrieveRunsResponse:
        """
        Get all runs for a cluster job, optionally filtered by cluster.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return self._get(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}/runs", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "attribute_sort_key": attribute_sort_key,
                        "attribute_sort_order": attribute_sort_order,
                        "cluster_id": cluster_id,
                        "limit": limit,
                        "offset": offset,
                    },
                    insight_retrieve_runs_params.InsightRetrieveRunsParams,
                ),
            ),
            cast_to=InsightRetrieveRunsResponse,
        )


class AsyncInsightsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncInsightsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncInsightsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncInsightsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncInsightsResourceWithStreamingResponse(self)

    async def create(
        self,
        session_id: str,
        *,
        attribute_schemas: Optional[Dict[str, object]] | Omit = omit,
        cluster_model: Optional[str] | Omit = omit,
        config_id: Optional[str] | Omit = omit,
        end_time: Union[str, datetime, None] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        hierarchy: Optional[Iterable[int]] | Omit = omit,
        is_scheduled: bool | Omit = omit,
        last_n_hours: Optional[int] | Omit = omit,
        model: Literal["openai", "anthropic"] | Omit = omit,
        name: Optional[str] | Omit = omit,
        partitions: Optional[Dict[str, str]] | Omit = omit,
        sample: Optional[float] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        summary_model: Optional[str] | Omit = omit,
        summary_prompt: Optional[str] | Omit = omit,
        user_context: Optional[Dict[str, str]] | Omit = omit,
        validate_model_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightCreateResponse:
        """
        Create an insights job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return await self._post(
            path_template("/api/v1/sessions/{session_id}/insights", session_id=session_id),
            body=await async_maybe_transform(
                {
                    "attribute_schemas": attribute_schemas,
                    "cluster_model": cluster_model,
                    "config_id": config_id,
                    "end_time": end_time,
                    "filter": filter,
                    "hierarchy": hierarchy,
                    "is_scheduled": is_scheduled,
                    "last_n_hours": last_n_hours,
                    "model": model,
                    "name": name,
                    "partitions": partitions,
                    "sample": sample,
                    "start_time": start_time,
                    "summary_model": summary_model,
                    "summary_prompt": summary_prompt,
                    "user_context": user_context,
                    "validate_model_secrets": validate_model_secrets,
                },
                insight_create_params.InsightCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightCreateResponse,
        )

    async def update(
        self,
        job_id: str,
        *,
        session_id: str,
        name: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightUpdateResponse:
        """
        Update a session cluster job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return await self._patch(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            body=await async_maybe_transform({"name": name}, insight_update_params.InsightUpdateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightUpdateResponse,
        )

    def list(
        self,
        session_id: str,
        *,
        config_id: Optional[str] | Omit = omit,
        legacy: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[InsightListResponse, AsyncOffsetPaginationInsightsClusteringJobs[InsightListResponse]]:
        """
        Get all clusters for a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        return self._get_api_list(
            path_template("/api/v1/sessions/{session_id}/insights", session_id=session_id),
            page=AsyncOffsetPaginationInsightsClusteringJobs[InsightListResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "config_id": config_id,
                        "legacy": legacy,
                        "limit": limit,
                        "offset": offset,
                    },
                    insight_list_params.InsightListParams,
                ),
            ),
            model=InsightListResponse,
        )

    async def delete(
        self,
        job_id: str,
        *,
        session_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightDeleteResponse:
        """
        Delete a session cluster job.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return await self._delete(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightDeleteResponse,
        )

    async def retrieve_job(
        self,
        job_id: str,
        *,
        session_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightRetrieveJobResponse:
        """
        Get a specific cluster job for a session.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return await self._get(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=InsightRetrieveJobResponse,
        )

    async def retrieve_runs(
        self,
        job_id: str,
        *,
        session_id: str,
        attribute_sort_key: Optional[str] | Omit = omit,
        attribute_sort_order: Optional[Literal["asc", "desc"]] | Omit = omit,
        cluster_id: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> InsightRetrieveRunsResponse:
        """
        Get all runs for a cluster job, optionally filtered by cluster.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not session_id:
            raise ValueError(f"Expected a non-empty value for `session_id` but received {session_id!r}")
        if not job_id:
            raise ValueError(f"Expected a non-empty value for `job_id` but received {job_id!r}")
        return await self._get(
            path_template("/api/v1/sessions/{session_id}/insights/{job_id}/runs", session_id=session_id, job_id=job_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "attribute_sort_key": attribute_sort_key,
                        "attribute_sort_order": attribute_sort_order,
                        "cluster_id": cluster_id,
                        "limit": limit,
                        "offset": offset,
                    },
                    insight_retrieve_runs_params.InsightRetrieveRunsParams,
                ),
            ),
            cast_to=InsightRetrieveRunsResponse,
        )


class InsightsResourceWithRawResponse:
    def __init__(self, insights: InsightsResource) -> None:
        self._insights = insights

        self.create = to_raw_response_wrapper(
            insights.create,
        )
        self.update = to_raw_response_wrapper(
            insights.update,
        )
        self.list = to_raw_response_wrapper(
            insights.list,
        )
        self.delete = to_raw_response_wrapper(
            insights.delete,
        )
        self.retrieve_job = to_raw_response_wrapper(
            insights.retrieve_job,
        )
        self.retrieve_runs = to_raw_response_wrapper(
            insights.retrieve_runs,
        )


class AsyncInsightsResourceWithRawResponse:
    def __init__(self, insights: AsyncInsightsResource) -> None:
        self._insights = insights

        self.create = async_to_raw_response_wrapper(
            insights.create,
        )
        self.update = async_to_raw_response_wrapper(
            insights.update,
        )
        self.list = async_to_raw_response_wrapper(
            insights.list,
        )
        self.delete = async_to_raw_response_wrapper(
            insights.delete,
        )
        self.retrieve_job = async_to_raw_response_wrapper(
            insights.retrieve_job,
        )
        self.retrieve_runs = async_to_raw_response_wrapper(
            insights.retrieve_runs,
        )


class InsightsResourceWithStreamingResponse:
    def __init__(self, insights: InsightsResource) -> None:
        self._insights = insights

        self.create = to_streamed_response_wrapper(
            insights.create,
        )
        self.update = to_streamed_response_wrapper(
            insights.update,
        )
        self.list = to_streamed_response_wrapper(
            insights.list,
        )
        self.delete = to_streamed_response_wrapper(
            insights.delete,
        )
        self.retrieve_job = to_streamed_response_wrapper(
            insights.retrieve_job,
        )
        self.retrieve_runs = to_streamed_response_wrapper(
            insights.retrieve_runs,
        )


class AsyncInsightsResourceWithStreamingResponse:
    def __init__(self, insights: AsyncInsightsResource) -> None:
        self._insights = insights

        self.create = async_to_streamed_response_wrapper(
            insights.create,
        )
        self.update = async_to_streamed_response_wrapper(
            insights.update,
        )
        self.list = async_to_streamed_response_wrapper(
            insights.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            insights.delete,
        )
        self.retrieve_job = async_to_streamed_response_wrapper(
            insights.retrieve_job,
        )
        self.retrieve_runs = async_to_streamed_response_wrapper(
            insights.retrieve_runs,
        )
