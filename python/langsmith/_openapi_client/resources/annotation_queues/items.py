# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable
from datetime import datetime
from typing_extensions import Literal

import httpx

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
from ...pagination import SyncItemsCursorGetPagination, AsyncItemsCursorGetPagination
from ..._base_client import AsyncPaginator, make_request_options
from ...types.annotation_queues import (
    item_list_params,
    item_create_params,
    item_update_params,
    item_delete_all_params,
    item_create_status_params,
    item_retrieve_count_params,
)
from ...types.annotation_queues.item_list_response import ItemListResponse
from ...types.annotation_queues.item_create_response import ItemCreateResponse
from ...types.annotation_queues.item_update_response import ItemUpdateResponse
from ...types.annotation_queues.item_delete_all_response import ItemDeleteAllResponse
from ...types.annotation_queues.item_create_status_response import ItemCreateStatusResponse
from ...types.annotation_queues.item_retrieve_count_response import ItemRetrieveCountResponse
from ...types.annotation_queues.item_retrieve_placement_response import ItemRetrievePlacementResponse

__all__ = ["ItemsResource", "AsyncItemsResource"]


class ItemsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ItemsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return ItemsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ItemsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return ItemsResourceWithStreamingResponse(self)

    def create(
        self,
        queue_id: str,
        *,
        extend_trace_retention: bool | Omit = omit,
        items: Iterable[item_create_params.Item] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemCreateResponse:
        """Add RUN or THREAD items to a single annotation queue.

        RUN items require run_id
        unless they are created from a suggested example. THREAD items require thread_id
        and project_id.

        Args:
          extend_trace_retention: Extend trace retention for added run items

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items", queue_id=queue_id),
            body=maybe_transform({"items": items}, item_create_params.ItemCreateParams),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"extend_trace_retention": extend_trace_retention}, item_create_params.ItemCreateParams
                ),
            ),
            cast_to=ItemCreateResponse,
        )

    def update(
        self,
        item_id: str,
        *,
        queue_id: str,
        added_at: Union[str, datetime] | Omit = omit,
        last_reviewed_time: Union[str, datetime] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemUpdateResponse:
        """
        Partially update mutable timestamps (added_at, last_reviewed_time) for a RUN or
        THREAD annotation queue item. Omit a field, or pass JSON null, to leave it
        unchanged.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return self._patch(
            path_template(
                "/api/v1/platform/annotation-queues/{queue_id}/items/{item_id}", queue_id=queue_id, item_id=item_id
            ),
            body=maybe_transform(
                {
                    "added_at": added_at,
                    "last_reviewed_time": last_reviewed_time,
                },
                item_update_params.ItemUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemUpdateResponse,
        )

    def list(
        self,
        queue_id: str,
        *,
        status: Literal["needs_my_review", "needs_others_review", "archived"],
        cursor: str | Omit = omit,
        direction: Literal["forward", "backward"] | Omit = omit,
        item_type: Literal["RUN", "THREAD"] | Omit = omit,
        page_size: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncItemsCursorGetPagination[ItemListResponse]:
        """
        List RUN and THREAD items in a single annotation queue for one review status
        section, with opaque cursor pagination. Optional item_type=RUN|THREAD filters
        the page. direction=backward returns items before the supplied cursor. The
        response contains item metadata only, not expanded run or thread payloads.
        status=archived returns items whose queue review requirements have been
        satisfied, not merely items the caller personally marked completed.

        Args:
          status: Review section: needs_my_review, needs_others_review, or archived

          cursor: Opaque pagination cursor

          direction: Pagination direction. backward requires cursor

          item_type: Filter to RUN or THREAD

          page_size: Page size (max 100)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get_api_list(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items", queue_id=queue_id),
            page=SyncItemsCursorGetPagination[ItemListResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "status": status,
                        "cursor": cursor,
                        "direction": direction,
                        "item_type": item_type,
                        "page_size": page_size,
                    },
                    item_list_params.ItemListParams,
                ),
            ),
            model=ItemListResponse,
        )

    def create_status(
        self,
        queue_item_id: str,
        *,
        override_added_at: str | Omit = omit,
        status: Literal["viewed", "completed"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemCreateStatusResponse:
        """Log the caller's reviewer status for a RUN or THREAD annotation queue item.

        A
        null status re-shows the item for this reviewer.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_item_id:
            raise ValueError(f"Expected a non-empty value for `queue_item_id` but received {queue_item_id!r}")
        return self._post(
            path_template(
                "/api/v1/platform/annotation-queues/items/{queue_item_id}/status", queue_item_id=queue_item_id
            ),
            body=maybe_transform(
                {
                    "override_added_at": override_added_at,
                    "status": status,
                },
                item_create_status_params.ItemCreateStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemCreateStatusResponse,
        )

    def delete_all(
        self,
        queue_id: str,
        *,
        item_ids: SequenceNotStr[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemDeleteAllResponse:
        """
        Remove RUN or THREAD items from a single annotation queue by item ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items/delete", queue_id=queue_id),
            body=maybe_transform({"item_ids": item_ids}, item_delete_all_params.ItemDeleteAllParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemDeleteAllResponse,
        )

    def retrieve_count(
        self,
        queue_id: str,
        *,
        status: str,
        end_time: str | Omit = omit,
        start_time: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemRetrieveCountResponse:
        """
        Returns the number of annotation queue items for the requested reviewer-specific
        or archived bucket.

        Args:
          status: Count bucket: all, needs_my_review, needs_others_review, or archived.

          end_time: Exclusive upper bound for archived item timestamp

          start_time: Exclusive lower bound for archived item timestamp

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items/count", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "status": status,
                        "end_time": end_time,
                        "start_time": start_time,
                    },
                    item_retrieve_count_params.ItemRetrieveCountParams,
                ),
            ),
            cast_to=ItemRetrieveCountResponse,
        )

    def retrieve_placement(
        self,
        item_id: str,
        *,
        queue_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemRetrievePlacementResponse:
        """
        Resolve a RUN or THREAD item to its current review section and zero-based
        position for deep linking.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return self._get(
            path_template(
                "/api/v1/platform/annotation-queues/{queue_id}/items/{item_id}/placement",
                queue_id=queue_id,
                item_id=item_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemRetrievePlacementResponse,
        )


class AsyncItemsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncItemsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncItemsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncItemsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncItemsResourceWithStreamingResponse(self)

    async def create(
        self,
        queue_id: str,
        *,
        extend_trace_retention: bool | Omit = omit,
        items: Iterable[item_create_params.Item] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemCreateResponse:
        """Add RUN or THREAD items to a single annotation queue.

        RUN items require run_id
        unless they are created from a suggested example. THREAD items require thread_id
        and project_id.

        Args:
          extend_trace_retention: Extend trace retention for added run items

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items", queue_id=queue_id),
            body=await async_maybe_transform({"items": items}, item_create_params.ItemCreateParams),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"extend_trace_retention": extend_trace_retention}, item_create_params.ItemCreateParams
                ),
            ),
            cast_to=ItemCreateResponse,
        )

    async def update(
        self,
        item_id: str,
        *,
        queue_id: str,
        added_at: Union[str, datetime] | Omit = omit,
        last_reviewed_time: Union[str, datetime] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemUpdateResponse:
        """
        Partially update mutable timestamps (added_at, last_reviewed_time) for a RUN or
        THREAD annotation queue item. Omit a field, or pass JSON null, to leave it
        unchanged.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return await self._patch(
            path_template(
                "/api/v1/platform/annotation-queues/{queue_id}/items/{item_id}", queue_id=queue_id, item_id=item_id
            ),
            body=await async_maybe_transform(
                {
                    "added_at": added_at,
                    "last_reviewed_time": last_reviewed_time,
                },
                item_update_params.ItemUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemUpdateResponse,
        )

    def list(
        self,
        queue_id: str,
        *,
        status: Literal["needs_my_review", "needs_others_review", "archived"],
        cursor: str | Omit = omit,
        direction: Literal["forward", "backward"] | Omit = omit,
        item_type: Literal["RUN", "THREAD"] | Omit = omit,
        page_size: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[ItemListResponse, AsyncItemsCursorGetPagination[ItemListResponse]]:
        """
        List RUN and THREAD items in a single annotation queue for one review status
        section, with opaque cursor pagination. Optional item_type=RUN|THREAD filters
        the page. direction=backward returns items before the supplied cursor. The
        response contains item metadata only, not expanded run or thread payloads.
        status=archived returns items whose queue review requirements have been
        satisfied, not merely items the caller personally marked completed.

        Args:
          status: Review section: needs_my_review, needs_others_review, or archived

          cursor: Opaque pagination cursor

          direction: Pagination direction. backward requires cursor

          item_type: Filter to RUN or THREAD

          page_size: Page size (max 100)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get_api_list(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items", queue_id=queue_id),
            page=AsyncItemsCursorGetPagination[ItemListResponse],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "status": status,
                        "cursor": cursor,
                        "direction": direction,
                        "item_type": item_type,
                        "page_size": page_size,
                    },
                    item_list_params.ItemListParams,
                ),
            ),
            model=ItemListResponse,
        )

    async def create_status(
        self,
        queue_item_id: str,
        *,
        override_added_at: str | Omit = omit,
        status: Literal["viewed", "completed"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemCreateStatusResponse:
        """Log the caller's reviewer status for a RUN or THREAD annotation queue item.

        A
        null status re-shows the item for this reviewer.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_item_id:
            raise ValueError(f"Expected a non-empty value for `queue_item_id` but received {queue_item_id!r}")
        return await self._post(
            path_template(
                "/api/v1/platform/annotation-queues/items/{queue_item_id}/status", queue_item_id=queue_item_id
            ),
            body=await async_maybe_transform(
                {
                    "override_added_at": override_added_at,
                    "status": status,
                },
                item_create_status_params.ItemCreateStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemCreateStatusResponse,
        )

    async def delete_all(
        self,
        queue_id: str,
        *,
        item_ids: SequenceNotStr[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemDeleteAllResponse:
        """
        Remove RUN or THREAD items from a single annotation queue by item ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items/delete", queue_id=queue_id),
            body=await async_maybe_transform({"item_ids": item_ids}, item_delete_all_params.ItemDeleteAllParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemDeleteAllResponse,
        )

    async def retrieve_count(
        self,
        queue_id: str,
        *,
        status: str,
        end_time: str | Omit = omit,
        start_time: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemRetrieveCountResponse:
        """
        Returns the number of annotation queue items for the requested reviewer-specific
        or archived bucket.

        Args:
          status: Count bucket: all, needs_my_review, needs_others_review, or archived.

          end_time: Exclusive upper bound for archived item timestamp

          start_time: Exclusive lower bound for archived item timestamp

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/api/v1/platform/annotation-queues/{queue_id}/items/count", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "status": status,
                        "end_time": end_time,
                        "start_time": start_time,
                    },
                    item_retrieve_count_params.ItemRetrieveCountParams,
                ),
            ),
            cast_to=ItemRetrieveCountResponse,
        )

    async def retrieve_placement(
        self,
        item_id: str,
        *,
        queue_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemRetrievePlacementResponse:
        """
        Resolve a RUN or THREAD item to its current review section and zero-based
        position for deep linking.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return await self._get(
            path_template(
                "/api/v1/platform/annotation-queues/{queue_id}/items/{item_id}/placement",
                queue_id=queue_id,
                item_id=item_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemRetrievePlacementResponse,
        )


class ItemsResourceWithRawResponse:
    def __init__(self, items: ItemsResource) -> None:
        self._items = items

        self.create = to_raw_response_wrapper(
            items.create,
        )
        self.update = to_raw_response_wrapper(
            items.update,
        )
        self.list = to_raw_response_wrapper(
            items.list,
        )
        self.create_status = to_raw_response_wrapper(
            items.create_status,
        )
        self.delete_all = to_raw_response_wrapper(
            items.delete_all,
        )
        self.retrieve_count = to_raw_response_wrapper(
            items.retrieve_count,
        )
        self.retrieve_placement = to_raw_response_wrapper(
            items.retrieve_placement,
        )


class AsyncItemsResourceWithRawResponse:
    def __init__(self, items: AsyncItemsResource) -> None:
        self._items = items

        self.create = async_to_raw_response_wrapper(
            items.create,
        )
        self.update = async_to_raw_response_wrapper(
            items.update,
        )
        self.list = async_to_raw_response_wrapper(
            items.list,
        )
        self.create_status = async_to_raw_response_wrapper(
            items.create_status,
        )
        self.delete_all = async_to_raw_response_wrapper(
            items.delete_all,
        )
        self.retrieve_count = async_to_raw_response_wrapper(
            items.retrieve_count,
        )
        self.retrieve_placement = async_to_raw_response_wrapper(
            items.retrieve_placement,
        )


class ItemsResourceWithStreamingResponse:
    def __init__(self, items: ItemsResource) -> None:
        self._items = items

        self.create = to_streamed_response_wrapper(
            items.create,
        )
        self.update = to_streamed_response_wrapper(
            items.update,
        )
        self.list = to_streamed_response_wrapper(
            items.list,
        )
        self.create_status = to_streamed_response_wrapper(
            items.create_status,
        )
        self.delete_all = to_streamed_response_wrapper(
            items.delete_all,
        )
        self.retrieve_count = to_streamed_response_wrapper(
            items.retrieve_count,
        )
        self.retrieve_placement = to_streamed_response_wrapper(
            items.retrieve_placement,
        )


class AsyncItemsResourceWithStreamingResponse:
    def __init__(self, items: AsyncItemsResource) -> None:
        self._items = items

        self.create = async_to_streamed_response_wrapper(
            items.create,
        )
        self.update = async_to_streamed_response_wrapper(
            items.update,
        )
        self.list = async_to_streamed_response_wrapper(
            items.list,
        )
        self.create_status = async_to_streamed_response_wrapper(
            items.create_status,
        )
        self.delete_all = async_to_streamed_response_wrapper(
            items.delete_all,
        )
        self.retrieve_count = async_to_streamed_response_wrapper(
            items.retrieve_count,
        )
        self.retrieve_placement = async_to_streamed_response_wrapper(
            items.retrieve_placement,
        )
