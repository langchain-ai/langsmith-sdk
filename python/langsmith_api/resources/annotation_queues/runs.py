# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, overload

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
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
from ...types.annotation_queues import run_list_params, run_create_params, run_update_params, run_delete_all_params
from ...types.annotation_queues.run_list_response import RunListResponse
from ...types.annotation_queues.run_create_response import RunCreateResponse

__all__ = ["RunsResource", "AsyncRunsResource"]


class RunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return RunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return RunsResourceWithStreamingResponse(self)

    @overload
    def create(
        self,
        queue_id: str,
        *,
        body: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    def create(
        self,
        queue_id: str,
        *,
        body: Iterable[run_create_params.RunsAnnotationQueueRunAddSchemaArrayBody],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    def create(
        self,
        queue_id: str,
        *,
        body: Iterable[run_create_params.Variant2Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @required_args(["body"])
    def create(
        self,
        queue_id: str,
        *,
        body: SequenceNotStr[str]
        | Iterable[run_create_params.RunsAnnotationQueueRunAddSchemaArrayBody]
        | Iterable[run_create_params.Variant2Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/runs", queue_id=queue_id),
            body=maybe_transform(body, SequenceNotStr[str]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RunCreateResponse,
        )

    def update(
        self,
        queue_run_id: str,
        *,
        queue_id: str,
        added_at: Union[str, datetime, None] | Omit = omit,
        last_reviewed_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update Run In Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not queue_run_id:
            raise ValueError(f"Expected a non-empty value for `queue_run_id` but received {queue_run_id!r}")
        return self._patch(
            path_template(
                "/api/v1/annotation-queues/{queue_id}/runs/{queue_run_id}", queue_id=queue_id, queue_run_id=queue_run_id
            ),
            body=maybe_transform(
                {
                    "added_at": added_at,
                    "last_reviewed_time": last_reviewed_time,
                },
                run_update_params.RunUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def list(
        self,
        queue_id: str,
        *,
        archived: Optional[bool] | Omit = omit,
        include_stats: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunListResponse:
        """
        Get Runs From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/runs", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "archived": archived,
                        "include_stats": include_stats,
                        "limit": limit,
                        "offset": offset,
                        "status": status,
                    },
                    run_list_params.RunListParams,
                ),
            ),
            cast_to=RunListResponse,
        )

    def delete_all(
        self,
        queue_id: str,
        *,
        delete_all: bool | Omit = omit,
        exclude_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Runs From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/runs/delete", queue_id=queue_id),
            body=maybe_transform(
                {
                    "delete_all": delete_all,
                    "exclude_run_ids": exclude_run_ids,
                    "run_ids": run_ids,
                },
                run_delete_all_params.RunDeleteAllParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def delete_queue(
        self,
        queue_run_id: str,
        *,
        queue_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Run From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not queue_run_id:
            raise ValueError(f"Expected a non-empty value for `queue_run_id` but received {queue_run_id!r}")
        return self._delete(
            path_template(
                "/api/v1/annotation-queues/{queue_id}/runs/{queue_run_id}", queue_id=queue_id, queue_run_id=queue_run_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncRunsResourceWithStreamingResponse(self)

    @overload
    async def create(
        self,
        queue_id: str,
        *,
        body: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    async def create(
        self,
        queue_id: str,
        *,
        body: Iterable[run_create_params.RunsAnnotationQueueRunAddSchemaArrayBody],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @overload
    async def create(
        self,
        queue_id: str,
        *,
        body: Iterable[run_create_params.Variant2Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        """
        Add Runs To Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        ...

    @required_args(["body"])
    async def create(
        self,
        queue_id: str,
        *,
        body: SequenceNotStr[str]
        | Iterable[run_create_params.RunsAnnotationQueueRunAddSchemaArrayBody]
        | Iterable[run_create_params.Variant2Body],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunCreateResponse:
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/runs", queue_id=queue_id),
            body=await async_maybe_transform(body, SequenceNotStr[str]),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RunCreateResponse,
        )

    async def update(
        self,
        queue_run_id: str,
        *,
        queue_id: str,
        added_at: Union[str, datetime, None] | Omit = omit,
        last_reviewed_time: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update Run In Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not queue_run_id:
            raise ValueError(f"Expected a non-empty value for `queue_run_id` but received {queue_run_id!r}")
        return await self._patch(
            path_template(
                "/api/v1/annotation-queues/{queue_id}/runs/{queue_run_id}", queue_id=queue_id, queue_run_id=queue_run_id
            ),
            body=await async_maybe_transform(
                {
                    "added_at": added_at,
                    "last_reviewed_time": last_reviewed_time,
                },
                run_update_params.RunUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def list(
        self,
        queue_id: str,
        *,
        archived: Optional[bool] | Omit = omit,
        include_stats: Optional[bool] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        status: Optional[Literal["needs_my_review", "needs_others_review", "completed"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunListResponse:
        """
        Get Runs From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/annotation-queues/{queue_id}/runs", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "archived": archived,
                        "include_stats": include_stats,
                        "limit": limit,
                        "offset": offset,
                        "status": status,
                    },
                    run_list_params.RunListParams,
                ),
            ),
            cast_to=RunListResponse,
        )

    async def delete_all(
        self,
        queue_id: str,
        *,
        delete_all: bool | Omit = omit,
        exclude_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Runs From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/api/v1/annotation-queues/{queue_id}/runs/delete", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "delete_all": delete_all,
                    "exclude_run_ids": exclude_run_ids,
                    "run_ids": run_ids,
                },
                run_delete_all_params.RunDeleteAllParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def delete_queue(
        self,
        queue_run_id: str,
        *,
        queue_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete Run From Annotation Queue

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not queue_run_id:
            raise ValueError(f"Expected a non-empty value for `queue_run_id` but received {queue_run_id!r}")
        return await self._delete(
            path_template(
                "/api/v1/annotation-queues/{queue_id}/runs/{queue_run_id}", queue_id=queue_id, queue_run_id=queue_run_id
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.create = to_raw_response_wrapper(
            runs.create,
        )
        self.update = to_raw_response_wrapper(
            runs.update,
        )
        self.list = to_raw_response_wrapper(
            runs.list,
        )
        self.delete_all = to_raw_response_wrapper(
            runs.delete_all,
        )
        self.delete_queue = to_raw_response_wrapper(
            runs.delete_queue,
        )


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.create = async_to_raw_response_wrapper(
            runs.create,
        )
        self.update = async_to_raw_response_wrapper(
            runs.update,
        )
        self.list = async_to_raw_response_wrapper(
            runs.list,
        )
        self.delete_all = async_to_raw_response_wrapper(
            runs.delete_all,
        )
        self.delete_queue = async_to_raw_response_wrapper(
            runs.delete_queue,
        )


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.create = to_streamed_response_wrapper(
            runs.create,
        )
        self.update = to_streamed_response_wrapper(
            runs.update,
        )
        self.list = to_streamed_response_wrapper(
            runs.list,
        )
        self.delete_all = to_streamed_response_wrapper(
            runs.delete_all,
        )
        self.delete_queue = to_streamed_response_wrapper(
            runs.delete_queue,
        )


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.create = async_to_streamed_response_wrapper(
            runs.create,
        )
        self.update = async_to_streamed_response_wrapper(
            runs.update,
        )
        self.list = async_to_streamed_response_wrapper(
            runs.list,
        )
        self.delete_all = async_to_streamed_response_wrapper(
            runs.delete_all,
        )
        self.delete_queue = async_to_streamed_response_wrapper(
            runs.delete_queue,
        )
