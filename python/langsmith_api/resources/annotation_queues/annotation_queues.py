# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal

import httpx

from .info import (
    InfoResource,
    AsyncInfoResource,
    InfoResourceWithRawResponse,
    AsyncInfoResourceWithRawResponse,
    InfoResourceWithStreamingResponse,
    AsyncInfoResourceWithStreamingResponse,
)
from .runs import (
    RunsResource,
    AsyncRunsResource,
    RunsResourceWithRawResponse,
    AsyncRunsResourceWithRawResponse,
    RunsResourceWithStreamingResponse,
    AsyncRunsResourceWithStreamingResponse,
)
from ...types import (
    annotation_queue_export_params,
    annotation_queue_update_params,
    annotation_queue_populate_params,
    annotation_queue_retrieve_run_params,
    annotation_queue_retrieve_size_params,
    annotation_queue_annotation_queues_params,
    annotation_queue_create_run_status_params,
    annotation_queue_retrieve_total_archived_params,
    annotation_queue_retrieve_annotation_queues_params,
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
from ...types.annotation_queue_schema import AnnotationQueueSchema
from ...types.annotation_queue_size_schema import AnnotationQueueSizeSchema
from ...types.annotation_queue_retrieve_response import AnnotationQueueRetrieveResponse
from ...types.run_schema_with_annotation_queue_info import RunSchemaWithAnnotationQueueInfo
from ...types.annotation_queue_retrieve_queues_response import AnnotationQueueRetrieveQueuesResponse
from ...types.annotation_queue_rubric_item_schema_param import AnnotationQueueRubricItemSchemaParam
from ...types.annotation_queue_retrieve_annotation_queues_response import (
    AnnotationQueueRetrieveAnnotationQueuesResponse,
)

__all__ = ["AnnotationQueuesResource", "AsyncAnnotationQueuesResource"]


class AnnotationQueuesResource(SyncAPIResource):
    @cached_property
    def runs(self) -> RunsResource:
        return RunsResource(self._client)

    @cached_property
    def info(self) -> InfoResource:
        return InfoResource(self._client)

    @cached_property
    def with_raw_response(self) -> AnnotationQueuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AnnotationQueuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AnnotationQueuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AnnotationQueuesResourceWithStreamingResponse(self)

    def retrieve(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueRetrieveResponse:
        """
        Get Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueRetrieveResponse,
        )

    def update(
        self,
        queue_id: str,
        *,
        default_dataset: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        enable_reservations: bool | Omit = omit,
        metadata: Optional[annotation_queue_update_params.Metadata] | Omit = omit,
        name: Optional[str] | Omit = omit,
        num_reviewers_per_item: Optional[annotation_queue_update_params.NumReviewersPerItem] | Omit = omit,
        reservation_minutes: Optional[int] | Omit = omit,
        reviewer_access_mode: Optional[Literal["any", "assigned"]] | Omit = omit,
        rubric_instructions: Optional[str] | Omit = omit,
        rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._patch(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            body=maybe_transform(
                {
                    "default_dataset": default_dataset,
                    "description": description,
                    "enable_reservations": enable_reservations,
                    "metadata": metadata,
                    "name": name,
                    "num_reviewers_per_item": num_reviewers_per_item,
                    "reservation_minutes": reservation_minutes,
                    "reviewer_access_mode": reviewer_access_mode,
                    "rubric_instructions": rubric_instructions,
                    "rubric_items": rubric_items,
                },
                annotation_queue_update_params.AnnotationQueueUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def delete(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._delete(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def annotation_queues(
        self,
        *,
        name: str,
        id: str | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        default_dataset: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        enable_reservations: Optional[bool] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        num_reviewers_per_item: Optional[int] | Omit = omit,
        reservation_minutes: Optional[int] | Omit = omit,
        reviewer_access_mode: str | Omit = omit,
        rubric_instructions: Optional[str] | Omit = omit,
        rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]] | Omit = omit,
        session_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        updated_at: Union[str, datetime] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSchema:
        """
        Create Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/annotation-queues",
            body=maybe_transform(
                {
                    "name": name,
                    "id": id,
                    "created_at": created_at,
                    "default_dataset": default_dataset,
                    "description": description,
                    "enable_reservations": enable_reservations,
                    "metadata": metadata,
                    "num_reviewers_per_item": num_reviewers_per_item,
                    "reservation_minutes": reservation_minutes,
                    "reviewer_access_mode": reviewer_access_mode,
                    "rubric_instructions": rubric_instructions,
                    "rubric_items": rubric_items,
                    "session_ids": session_ids,
                    "updated_at": updated_at,
                },
                annotation_queue_annotation_queues_params.AnnotationQueueAnnotationQueuesParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueSchema,
        )

    def create_run_status(
        self,
        annotation_queue_run_id: str,
        *,
        override_added_at: Union[str, datetime, None] | Omit = omit,
        status: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create Identity Annotation Queue Run Status

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not annotation_queue_run_id:
            raise ValueError(
                f"Expected a non-empty value for `annotation_queue_run_id` but received {annotation_queue_run_id!r}"
            )
        return self._post(
            path_template(
                "/api/v1/annotation-queues/status/{annotation_queue_run_id}",
                annotation_queue_run_id=annotation_queue_run_id,
            ),
            body=maybe_transform(
                {
                    "override_added_at": override_added_at,
                    "status": status,
                },
                annotation_queue_create_run_status_params.AnnotationQueueCreateRunStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def export(
        self,
        queue_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        include_annotator_detail: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Export Annotation Queue Archived Runs

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/export", queue_id=queue_id),
            body=maybe_transform(
                {
                    "end_time": end_time,
                    "include_annotator_detail": include_annotator_detail,
                    "start_time": start_time,
                },
                annotation_queue_export_params.AnnotationQueueExportParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def populate(
        self,
        *,
        queue_id: str,
        session_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Populate annotation queue with runs from an experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/annotation-queues/populate",
            body=maybe_transform(
                {
                    "queue_id": queue_id,
                    "session_ids": session_ids,
                },
                annotation_queue_populate_params.AnnotationQueuePopulateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def retrieve_annotation_queues(
        self,
        *,
        assigned_to_me: bool | Omit = omit,
        dataset_id: Optional[str] | Omit = omit,
        ids: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        queue_type: Optional[Literal["single", "pairwise"]] | Omit = omit,
        sort_by: Optional[str] | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[AnnotationQueueRetrieveAnnotationQueuesResponse]:
        """
        Get Annotation Queues

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/annotation-queues",
            page=SyncOffsetPaginationTopLevelArray[AnnotationQueueRetrieveAnnotationQueuesResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "assigned_to_me": assigned_to_me,
                        "dataset_id": dataset_id,
                        "ids": ids,
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "queue_type": queue_type,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                    },
                    annotation_queue_retrieve_annotation_queues_params.AnnotationQueueRetrieveAnnotationQueuesParams,
                ),
            ),
            model=AnnotationQueueRetrieveAnnotationQueuesResponse,
        )

    def retrieve_queues(
        self,
        run_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueRetrieveQueuesResponse:
        """
        Get Annotation Queues For Run

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{run_id}/queues", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueRetrieveQueuesResponse,
        )

    def retrieve_run(
        self,
        index: int,
        *,
        queue_id: str,
        include_extra: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunSchemaWithAnnotationQueueInfo:
        """
        Get a run from an annotation queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/run/{index}", queue_id=queue_id, index=index),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"include_extra": include_extra},
                    annotation_queue_retrieve_run_params.AnnotationQueueRetrieveRunParams,
                ),
            ),
            cast_to=RunSchemaWithAnnotationQueueInfo,
        )

    def retrieve_size(
        self,
        queue_id: str,
        *,
        status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Size From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/size", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"status": status}, annotation_queue_retrieve_size_params.AnnotationQueueRetrieveSizeParams
                ),
            ),
            cast_to=AnnotationQueueSizeSchema,
        )

    def retrieve_total_archived(
        self,
        queue_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Total Archived From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/total_archived", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "end_time": end_time,
                        "start_time": start_time,
                    },
                    annotation_queue_retrieve_total_archived_params.AnnotationQueueRetrieveTotalArchivedParams,
                ),
            ),
            cast_to=AnnotationQueueSizeSchema,
        )

    def retrieve_total_size(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Total Size From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/total_size", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueSizeSchema,
        )


class AsyncAnnotationQueuesResource(AsyncAPIResource):
    @cached_property
    def runs(self) -> AsyncRunsResource:
        return AsyncRunsResource(self._client)

    @cached_property
    def info(self) -> AsyncInfoResource:
        return AsyncInfoResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncAnnotationQueuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAnnotationQueuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAnnotationQueuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncAnnotationQueuesResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueRetrieveResponse:
        """
        Get Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueRetrieveResponse,
        )

    async def update(
        self,
        queue_id: str,
        *,
        default_dataset: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        enable_reservations: bool | Omit = omit,
        metadata: Optional[annotation_queue_update_params.Metadata] | Omit = omit,
        name: Optional[str] | Omit = omit,
        num_reviewers_per_item: Optional[annotation_queue_update_params.NumReviewersPerItem] | Omit = omit,
        reservation_minutes: Optional[int] | Omit = omit,
        reviewer_access_mode: Optional[Literal["any", "assigned"]] | Omit = omit,
        rubric_instructions: Optional[str] | Omit = omit,
        rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._patch(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "default_dataset": default_dataset,
                    "description": description,
                    "enable_reservations": enable_reservations,
                    "metadata": metadata,
                    "name": name,
                    "num_reviewers_per_item": num_reviewers_per_item,
                    "reservation_minutes": reservation_minutes,
                    "reviewer_access_mode": reviewer_access_mode,
                    "rubric_instructions": rubric_instructions,
                    "rubric_items": rubric_items,
                },
                annotation_queue_update_params.AnnotationQueueUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def delete(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._delete(
            path_template("/api/v1/annotation-queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def annotation_queues(
        self,
        *,
        name: str,
        id: str | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        default_dataset: Optional[str] | Omit = omit,
        description: Optional[str] | Omit = omit,
        enable_reservations: Optional[bool] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        num_reviewers_per_item: Optional[int] | Omit = omit,
        reservation_minutes: Optional[int] | Omit = omit,
        reviewer_access_mode: str | Omit = omit,
        rubric_instructions: Optional[str] | Omit = omit,
        rubric_items: Optional[Iterable[AnnotationQueueRubricItemSchemaParam]] | Omit = omit,
        session_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        updated_at: Union[str, datetime] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSchema:
        """
        Create Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/annotation-queues",
            body=await async_maybe_transform(
                {
                    "name": name,
                    "id": id,
                    "created_at": created_at,
                    "default_dataset": default_dataset,
                    "description": description,
                    "enable_reservations": enable_reservations,
                    "metadata": metadata,
                    "num_reviewers_per_item": num_reviewers_per_item,
                    "reservation_minutes": reservation_minutes,
                    "reviewer_access_mode": reviewer_access_mode,
                    "rubric_instructions": rubric_instructions,
                    "rubric_items": rubric_items,
                    "session_ids": session_ids,
                    "updated_at": updated_at,
                },
                annotation_queue_annotation_queues_params.AnnotationQueueAnnotationQueuesParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueSchema,
        )

    async def create_run_status(
        self,
        annotation_queue_run_id: str,
        *,
        override_added_at: Union[str, datetime, None] | Omit = omit,
        status: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Create Identity Annotation Queue Run Status

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not annotation_queue_run_id:
            raise ValueError(
                f"Expected a non-empty value for `annotation_queue_run_id` but received {annotation_queue_run_id!r}"
            )
        return await self._post(
            path_template(
                "/api/v1/annotation-queues/status/{annotation_queue_run_id}",
                annotation_queue_run_id=annotation_queue_run_id,
            ),
            body=await async_maybe_transform(
                {
                    "override_added_at": override_added_at,
                    "status": status,
                },
                annotation_queue_create_run_status_params.AnnotationQueueCreateRunStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def export(
        self,
        queue_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        include_annotator_detail: bool | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Export Annotation Queue Archived Runs

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/export", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "end_time": end_time,
                    "include_annotator_detail": include_annotator_detail,
                    "start_time": start_time,
                },
                annotation_queue_export_params.AnnotationQueueExportParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def populate(
        self,
        *,
        queue_id: str,
        session_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Populate annotation queue with runs from an experiment.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/annotation-queues/populate",
            body=await async_maybe_transform(
                {
                    "queue_id": queue_id,
                    "session_ids": session_ids,
                },
                annotation_queue_populate_params.AnnotationQueuePopulateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def retrieve_annotation_queues(
        self,
        *,
        assigned_to_me: bool | Omit = omit,
        dataset_id: Optional[str] | Omit = omit,
        ids: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: int | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        queue_type: Optional[Literal["single", "pairwise"]] | Omit = omit,
        sort_by: Optional[str] | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[
        AnnotationQueueRetrieveAnnotationQueuesResponse,
        AsyncOffsetPaginationTopLevelArray[AnnotationQueueRetrieveAnnotationQueuesResponse],
    ]:
        """
        Get Annotation Queues

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/annotation-queues",
            page=AsyncOffsetPaginationTopLevelArray[AnnotationQueueRetrieveAnnotationQueuesResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "assigned_to_me": assigned_to_me,
                        "dataset_id": dataset_id,
                        "ids": ids,
                        "limit": limit,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "queue_type": queue_type,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                    },
                    annotation_queue_retrieve_annotation_queues_params.AnnotationQueueRetrieveAnnotationQueuesParams,
                ),
            ),
            model=AnnotationQueueRetrieveAnnotationQueuesResponse,
        )

    async def retrieve_queues(
        self,
        run_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueRetrieveQueuesResponse:
        """
        Get Annotation Queues For Run

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{run_id}/queues", run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueRetrieveQueuesResponse,
        )

    async def retrieve_run(
        self,
        index: int,
        *,
        queue_id: str,
        include_extra: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunSchemaWithAnnotationQueueInfo:
        """
        Get a run from an annotation queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/run/{index}", queue_id=queue_id, index=index),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"include_extra": include_extra},
                    annotation_queue_retrieve_run_params.AnnotationQueueRetrieveRunParams,
                ),
            ),
            cast_to=RunSchemaWithAnnotationQueueInfo,
        )

    async def retrieve_size(
        self,
        queue_id: str,
        *,
        status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Size From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/size", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"status": status}, annotation_queue_retrieve_size_params.AnnotationQueueRetrieveSizeParams
                ),
            ),
            cast_to=AnnotationQueueSizeSchema,
        )

    async def retrieve_total_archived(
        self,
        queue_id: str,
        *,
        end_time: Union[str, datetime, None] | Omit = omit,
        start_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Total Archived From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/total_archived", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "end_time": end_time,
                        "start_time": start_time,
                    },
                    annotation_queue_retrieve_total_archived_params.AnnotationQueueRetrieveTotalArchivedParams,
                ),
            ),
            cast_to=AnnotationQueueSizeSchema,
        )

    async def retrieve_total_size(
        self,
        queue_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueSizeSchema:
        """
        Get Total Size From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/total_size", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueSizeSchema,
        )


class AnnotationQueuesResourceWithRawResponse:
    def __init__(self, annotation_queues: AnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.retrieve = to_raw_response_wrapper(
            annotation_queues.retrieve,
        )
        self.update = to_raw_response_wrapper(
            annotation_queues.update,
        )
        self.delete = to_raw_response_wrapper(
            annotation_queues.delete,
        )
        self.annotation_queues = to_raw_response_wrapper(
            annotation_queues.annotation_queues,
        )
        self.create_run_status = to_raw_response_wrapper(
            annotation_queues.create_run_status,
        )
        self.export = to_raw_response_wrapper(
            annotation_queues.export,
        )
        self.populate = to_raw_response_wrapper(
            annotation_queues.populate,
        )
        self.retrieve_annotation_queues = to_raw_response_wrapper(
            annotation_queues.retrieve_annotation_queues,
        )
        self.retrieve_queues = to_raw_response_wrapper(
            annotation_queues.retrieve_queues,
        )
        self.retrieve_run = to_raw_response_wrapper(
            annotation_queues.retrieve_run,
        )
        self.retrieve_size = to_raw_response_wrapper(
            annotation_queues.retrieve_size,
        )
        self.retrieve_total_archived = to_raw_response_wrapper(
            annotation_queues.retrieve_total_archived,
        )
        self.retrieve_total_size = to_raw_response_wrapper(
            annotation_queues.retrieve_total_size,
        )

    @cached_property
    def runs(self) -> RunsResourceWithRawResponse:
        return RunsResourceWithRawResponse(self._annotation_queues.runs)

    @cached_property
    def info(self) -> InfoResourceWithRawResponse:
        return InfoResourceWithRawResponse(self._annotation_queues.info)


class AsyncAnnotationQueuesResourceWithRawResponse:
    def __init__(self, annotation_queues: AsyncAnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.retrieve = async_to_raw_response_wrapper(
            annotation_queues.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            annotation_queues.update,
        )
        self.delete = async_to_raw_response_wrapper(
            annotation_queues.delete,
        )
        self.annotation_queues = async_to_raw_response_wrapper(
            annotation_queues.annotation_queues,
        )
        self.create_run_status = async_to_raw_response_wrapper(
            annotation_queues.create_run_status,
        )
        self.export = async_to_raw_response_wrapper(
            annotation_queues.export,
        )
        self.populate = async_to_raw_response_wrapper(
            annotation_queues.populate,
        )
        self.retrieve_annotation_queues = async_to_raw_response_wrapper(
            annotation_queues.retrieve_annotation_queues,
        )
        self.retrieve_queues = async_to_raw_response_wrapper(
            annotation_queues.retrieve_queues,
        )
        self.retrieve_run = async_to_raw_response_wrapper(
            annotation_queues.retrieve_run,
        )
        self.retrieve_size = async_to_raw_response_wrapper(
            annotation_queues.retrieve_size,
        )
        self.retrieve_total_archived = async_to_raw_response_wrapper(
            annotation_queues.retrieve_total_archived,
        )
        self.retrieve_total_size = async_to_raw_response_wrapper(
            annotation_queues.retrieve_total_size,
        )

    @cached_property
    def runs(self) -> AsyncRunsResourceWithRawResponse:
        return AsyncRunsResourceWithRawResponse(self._annotation_queues.runs)

    @cached_property
    def info(self) -> AsyncInfoResourceWithRawResponse:
        return AsyncInfoResourceWithRawResponse(self._annotation_queues.info)


class AnnotationQueuesResourceWithStreamingResponse:
    def __init__(self, annotation_queues: AnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.retrieve = to_streamed_response_wrapper(
            annotation_queues.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            annotation_queues.update,
        )
        self.delete = to_streamed_response_wrapper(
            annotation_queues.delete,
        )
        self.annotation_queues = to_streamed_response_wrapper(
            annotation_queues.annotation_queues,
        )
        self.create_run_status = to_streamed_response_wrapper(
            annotation_queues.create_run_status,
        )
        self.export = to_streamed_response_wrapper(
            annotation_queues.export,
        )
        self.populate = to_streamed_response_wrapper(
            annotation_queues.populate,
        )
        self.retrieve_annotation_queues = to_streamed_response_wrapper(
            annotation_queues.retrieve_annotation_queues,
        )
        self.retrieve_queues = to_streamed_response_wrapper(
            annotation_queues.retrieve_queues,
        )
        self.retrieve_run = to_streamed_response_wrapper(
            annotation_queues.retrieve_run,
        )
        self.retrieve_size = to_streamed_response_wrapper(
            annotation_queues.retrieve_size,
        )
        self.retrieve_total_archived = to_streamed_response_wrapper(
            annotation_queues.retrieve_total_archived,
        )
        self.retrieve_total_size = to_streamed_response_wrapper(
            annotation_queues.retrieve_total_size,
        )

    @cached_property
    def runs(self) -> RunsResourceWithStreamingResponse:
        return RunsResourceWithStreamingResponse(self._annotation_queues.runs)

    @cached_property
    def info(self) -> InfoResourceWithStreamingResponse:
        return InfoResourceWithStreamingResponse(self._annotation_queues.info)


class AsyncAnnotationQueuesResourceWithStreamingResponse:
    def __init__(self, annotation_queues: AsyncAnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.retrieve = async_to_streamed_response_wrapper(
            annotation_queues.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            annotation_queues.update,
        )
        self.delete = async_to_streamed_response_wrapper(
            annotation_queues.delete,
        )
        self.annotation_queues = async_to_streamed_response_wrapper(
            annotation_queues.annotation_queues,
        )
        self.create_run_status = async_to_streamed_response_wrapper(
            annotation_queues.create_run_status,
        )
        self.export = async_to_streamed_response_wrapper(
            annotation_queues.export,
        )
        self.populate = async_to_streamed_response_wrapper(
            annotation_queues.populate,
        )
        self.retrieve_annotation_queues = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_annotation_queues,
        )
        self.retrieve_queues = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_queues,
        )
        self.retrieve_run = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_run,
        )
        self.retrieve_size = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_size,
        )
        self.retrieve_total_archived = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_total_archived,
        )
        self.retrieve_total_size = async_to_streamed_response_wrapper(
            annotation_queues.retrieve_total_size,
        )

    @cached_property
    def runs(self) -> AsyncRunsResourceWithStreamingResponse:
        return AsyncRunsResourceWithStreamingResponse(self._annotation_queues.runs)

    @cached_property
    def info(self) -> AsyncInfoResourceWithStreamingResponse:
        return AsyncInfoResourceWithStreamingResponse(self._annotation_queues.info)
