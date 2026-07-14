# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..types import (
    OnlineEvaluatorType,
    online_evaluator_list_params,
    online_evaluator_spend_params,
    online_evaluator_create_params,
    online_evaluator_delete_params,
    online_evaluator_update_params,
    online_evaluator_bulk_delete_params,
)
from .._types import Body, Omit, Query, Headers, NoneType, NotGiven, SequenceNotStr, omit, not_given
from .._utils import path_template, maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..pagination import SyncOffsetPaginationOnlineEvaluators, AsyncOffsetPaginationOnlineEvaluators
from .._base_client import AsyncPaginator, make_request_options
from ..types.online_evaluator import OnlineEvaluator
from ..types.online_evaluator_type import OnlineEvaluatorType
from ..types.bulk_delete_evaluators_response import BulkDeleteEvaluatorsResponse
from ..types.create_online_evaluator_response import CreateOnlineEvaluatorResponse
from ..types.update_online_evaluator_response import UpdateOnlineEvaluatorResponse
from ..types.get_online_evaluator_spend_response import GetOnlineEvaluatorSpendResponse
from ..types.create_online_llm_evaluator_request_param import CreateOnlineLlmEvaluatorRequestParam
from ..types.update_online_llm_evaluator_request_param import UpdateOnlineLlmEvaluatorRequestParam
from ..types.create_online_code_evaluator_request_param import CreateOnlineCodeEvaluatorRequestParam
from ..types.update_online_code_evaluator_request_param import UpdateOnlineCodeEvaluatorRequestParam

__all__ = ["OnlineEvaluatorsResource", "AsyncOnlineEvaluatorsResource"]


class OnlineEvaluatorsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> OnlineEvaluatorsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return OnlineEvaluatorsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> OnlineEvaluatorsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return OnlineEvaluatorsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        code_evaluator: CreateOnlineCodeEvaluatorRequestParam | Omit = omit,
        llm_evaluator: CreateOnlineLlmEvaluatorRequestParam | Omit = omit,
        name: str | Omit = omit,
        type: OnlineEvaluatorType | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateOnlineEvaluatorResponse:
        """
        Create a new LLM or code evaluator for the current workspace.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/v1/platform/evaluators",
            body=maybe_transform(
                {
                    "code_evaluator": code_evaluator,
                    "llm_evaluator": llm_evaluator,
                    "name": name,
                    "type": type,
                },
                online_evaluator_create_params.OnlineEvaluatorCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateOnlineEvaluatorResponse,
        )

    def retrieve(
        self,
        evaluator_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> OnlineEvaluator:
        """
        Retrieve a single evaluator by its ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        return self._get(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=OnlineEvaluator,
        )

    def update(
        self,
        evaluator_id: str,
        *,
        code_evaluator: UpdateOnlineCodeEvaluatorRequestParam | Omit = omit,
        llm_evaluator: UpdateOnlineLlmEvaluatorRequestParam | Omit = omit,
        name: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> UpdateOnlineEvaluatorResponse:
        """
        Update an existing evaluator's name, LLM configuration, or code configuration.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        return self._patch(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            body=maybe_transform(
                {
                    "code_evaluator": code_evaluator,
                    "llm_evaluator": llm_evaluator,
                    "name": name,
                },
                online_evaluator_update_params.OnlineEvaluatorUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=UpdateOnlineEvaluatorResponse,
        )

    def list(
        self,
        *,
        feedback_key: str | Omit = omit,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        resource_id: SequenceNotStr[str] | Omit = omit,
        sort_by: str | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: SequenceNotStr[str] | Omit = omit,
        type: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationOnlineEvaluators[OnlineEvaluator]:
        """
        List evaluators for the current workspace, with optional filtering by type,
        name, tag, feedback key, or resource ID.

        Args:
          feedback_key: Filter by feedback key

          limit: Maximum number of results (1-100)

          name_contains: Filter by name substring (also searches creator names)

          offset: Offset for pagination

          resource_id: Filter by resource IDs

          sort_by: Field to sort by

          sort_by_desc: Sort in descending order

          tag_value_id: Filter by tag value IDs

          type: Filter by evaluator type

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v1/platform/evaluators",
            page=SyncOffsetPaginationOnlineEvaluators[OnlineEvaluator],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "feedback_key": feedback_key,
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                        "resource_id": resource_id,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                        "type": type,
                    },
                    online_evaluator_list_params.OnlineEvaluatorListParams,
                ),
            ),
            model=OnlineEvaluator,
        )

    def delete(
        self,
        evaluator_id: str,
        *,
        delete_run_rules: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Delete an evaluator.

        When delete_run_rules is true, all run rules referencing
        this evaluator are deleted first (same tenant). Associated llm_evaluators and
        code_evaluators rows are removed by foreign-key cascade when the evaluator row
        is deleted.

        Args:
          delete_run_rules: When true, delete all run rules for this evaluator before deleting the evaluator

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"delete_run_rules": delete_run_rules}, online_evaluator_delete_params.OnlineEvaluatorDeleteParams
                ),
            ),
            cast_to=NoneType,
        )

    def bulk_delete(
        self,
        *,
        evaluator_ids: SequenceNotStr[str],
        delete_run_rules: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkDeleteEvaluatorsResponse:
        """Delete multiple evaluators by their IDs.

        Returns per-item success/failure.

        Args:
          evaluator_ids: Evaluator IDs to delete

          delete_run_rules: When true, delete all run rules for this evaluator before deleting the evaluator

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._delete(
            "/v1/platform/evaluators",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "evaluator_ids": evaluator_ids,
                        "delete_run_rules": delete_run_rules,
                    },
                    online_evaluator_bulk_delete_params.OnlineEvaluatorBulkDeleteParams,
                ),
            ),
            cast_to=BulkDeleteEvaluatorsResponse,
        )

    def spend(
        self,
        *,
        period_start: str,
        dataset_id: str | Omit = omit,
        evaluator_id: str | Omit = omit,
        feedback_key: str | Omit = omit,
        group_by: str | Omit = omit,
        resource_id: SequenceNotStr[str] | Omit = omit,
        session_id: str | Omit = omit,
        type: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GetOnlineEvaluatorSpendResponse:
        """
        Returns per-day LLM evaluator spend for the requested 7-day period, grouped by
        evaluator, resource, or run rule. Exactly one of group_by, evaluator_id,
        session_id, or dataset_id is required. resource_id, type, and feedback_key may
        be supplied with group_by to narrow listing aggregations.

        Args:
          period_start: Start of the 7-day window (YYYY-MM-DD).

          dataset_id: Filter to a specific dataset (UUID). Mutually exclusive with group_by.

          evaluator_id: Filter to a specific evaluator (UUID). Mutually exclusive with group_by.

          feedback_key: Filter grouped results by evaluator feedback key. Only valid with group_by.

          group_by: Aggregation mode: 'evaluator', 'resource', or 'run_rule'. Mutually exclusive
              with entity filters.

          resource_id: Filter grouped results to evaluators attached to all supplied project or dataset
              IDs. Only valid with group_by.

          session_id: Filter to a specific project (UUID). Mutually exclusive with group_by.

          type: Filter grouped results by evaluator type: 'llm' or 'code'. Only valid with
              group_by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/v1/platform/evaluators/spend",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "period_start": period_start,
                        "dataset_id": dataset_id,
                        "evaluator_id": evaluator_id,
                        "feedback_key": feedback_key,
                        "group_by": group_by,
                        "resource_id": resource_id,
                        "session_id": session_id,
                        "type": type,
                    },
                    online_evaluator_spend_params.OnlineEvaluatorSpendParams,
                ),
            ),
            cast_to=GetOnlineEvaluatorSpendResponse,
        )


class AsyncOnlineEvaluatorsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncOnlineEvaluatorsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncOnlineEvaluatorsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncOnlineEvaluatorsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncOnlineEvaluatorsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        code_evaluator: CreateOnlineCodeEvaluatorRequestParam | Omit = omit,
        llm_evaluator: CreateOnlineLlmEvaluatorRequestParam | Omit = omit,
        name: str | Omit = omit,
        type: OnlineEvaluatorType | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateOnlineEvaluatorResponse:
        """
        Create a new LLM or code evaluator for the current workspace.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/v1/platform/evaluators",
            body=await async_maybe_transform(
                {
                    "code_evaluator": code_evaluator,
                    "llm_evaluator": llm_evaluator,
                    "name": name,
                    "type": type,
                },
                online_evaluator_create_params.OnlineEvaluatorCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateOnlineEvaluatorResponse,
        )

    async def retrieve(
        self,
        evaluator_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> OnlineEvaluator:
        """
        Retrieve a single evaluator by its ID.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        return await self._get(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=OnlineEvaluator,
        )

    async def update(
        self,
        evaluator_id: str,
        *,
        code_evaluator: UpdateOnlineCodeEvaluatorRequestParam | Omit = omit,
        llm_evaluator: UpdateOnlineLlmEvaluatorRequestParam | Omit = omit,
        name: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> UpdateOnlineEvaluatorResponse:
        """
        Update an existing evaluator's name, LLM configuration, or code configuration.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        return await self._patch(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            body=await async_maybe_transform(
                {
                    "code_evaluator": code_evaluator,
                    "llm_evaluator": llm_evaluator,
                    "name": name,
                },
                online_evaluator_update_params.OnlineEvaluatorUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=UpdateOnlineEvaluatorResponse,
        )

    def list(
        self,
        *,
        feedback_key: str | Omit = omit,
        limit: int | Omit = omit,
        name_contains: str | Omit = omit,
        offset: int | Omit = omit,
        resource_id: SequenceNotStr[str] | Omit = omit,
        sort_by: str | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: SequenceNotStr[str] | Omit = omit,
        type: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[OnlineEvaluator, AsyncOffsetPaginationOnlineEvaluators[OnlineEvaluator]]:
        """
        List evaluators for the current workspace, with optional filtering by type,
        name, tag, feedback key, or resource ID.

        Args:
          feedback_key: Filter by feedback key

          limit: Maximum number of results (1-100)

          name_contains: Filter by name substring (also searches creator names)

          offset: Offset for pagination

          resource_id: Filter by resource IDs

          sort_by: Field to sort by

          sort_by_desc: Sort in descending order

          tag_value_id: Filter by tag value IDs

          type: Filter by evaluator type

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v1/platform/evaluators",
            page=AsyncOffsetPaginationOnlineEvaluators[OnlineEvaluator],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "feedback_key": feedback_key,
                        "limit": limit,
                        "name_contains": name_contains,
                        "offset": offset,
                        "resource_id": resource_id,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                        "type": type,
                    },
                    online_evaluator_list_params.OnlineEvaluatorListParams,
                ),
            ),
            model=OnlineEvaluator,
        )

    async def delete(
        self,
        evaluator_id: str,
        *,
        delete_run_rules: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """Delete an evaluator.

        When delete_run_rules is true, all run rules referencing
        this evaluator are deleted first (same tenant). Associated llm_evaluators and
        code_evaluators rows are removed by foreign-key cascade when the evaluator row
        is deleted.

        Args:
          delete_run_rules: When true, delete all run rules for this evaluator before deleting the evaluator

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not evaluator_id:
            raise ValueError(f"Expected a non-empty value for `evaluator_id` but received {evaluator_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template("/v1/platform/evaluators/{evaluator_id}", evaluator_id=evaluator_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"delete_run_rules": delete_run_rules}, online_evaluator_delete_params.OnlineEvaluatorDeleteParams
                ),
            ),
            cast_to=NoneType,
        )

    async def bulk_delete(
        self,
        *,
        evaluator_ids: SequenceNotStr[str],
        delete_run_rules: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> BulkDeleteEvaluatorsResponse:
        """Delete multiple evaluators by their IDs.

        Returns per-item success/failure.

        Args:
          evaluator_ids: Evaluator IDs to delete

          delete_run_rules: When true, delete all run rules for this evaluator before deleting the evaluator

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._delete(
            "/v1/platform/evaluators",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "evaluator_ids": evaluator_ids,
                        "delete_run_rules": delete_run_rules,
                    },
                    online_evaluator_bulk_delete_params.OnlineEvaluatorBulkDeleteParams,
                ),
            ),
            cast_to=BulkDeleteEvaluatorsResponse,
        )

    async def spend(
        self,
        *,
        period_start: str,
        dataset_id: str | Omit = omit,
        evaluator_id: str | Omit = omit,
        feedback_key: str | Omit = omit,
        group_by: str | Omit = omit,
        resource_id: SequenceNotStr[str] | Omit = omit,
        session_id: str | Omit = omit,
        type: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GetOnlineEvaluatorSpendResponse:
        """
        Returns per-day LLM evaluator spend for the requested 7-day period, grouped by
        evaluator, resource, or run rule. Exactly one of group_by, evaluator_id,
        session_id, or dataset_id is required. resource_id, type, and feedback_key may
        be supplied with group_by to narrow listing aggregations.

        Args:
          period_start: Start of the 7-day window (YYYY-MM-DD).

          dataset_id: Filter to a specific dataset (UUID). Mutually exclusive with group_by.

          evaluator_id: Filter to a specific evaluator (UUID). Mutually exclusive with group_by.

          feedback_key: Filter grouped results by evaluator feedback key. Only valid with group_by.

          group_by: Aggregation mode: 'evaluator', 'resource', or 'run_rule'. Mutually exclusive
              with entity filters.

          resource_id: Filter grouped results to evaluators attached to all supplied project or dataset
              IDs. Only valid with group_by.

          session_id: Filter to a specific project (UUID). Mutually exclusive with group_by.

          type: Filter grouped results by evaluator type: 'llm' or 'code'. Only valid with
              group_by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/v1/platform/evaluators/spend",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "period_start": period_start,
                        "dataset_id": dataset_id,
                        "evaluator_id": evaluator_id,
                        "feedback_key": feedback_key,
                        "group_by": group_by,
                        "resource_id": resource_id,
                        "session_id": session_id,
                        "type": type,
                    },
                    online_evaluator_spend_params.OnlineEvaluatorSpendParams,
                ),
            ),
            cast_to=GetOnlineEvaluatorSpendResponse,
        )


class OnlineEvaluatorsResourceWithRawResponse:
    def __init__(self, online_evaluators: OnlineEvaluatorsResource) -> None:
        self._online_evaluators = online_evaluators

        self.create = to_raw_response_wrapper(
            online_evaluators.create,
        )
        self.retrieve = to_raw_response_wrapper(
            online_evaluators.retrieve,
        )
        self.update = to_raw_response_wrapper(
            online_evaluators.update,
        )
        self.list = to_raw_response_wrapper(
            online_evaluators.list,
        )
        self.delete = to_raw_response_wrapper(
            online_evaluators.delete,
        )
        self.bulk_delete = to_raw_response_wrapper(
            online_evaluators.bulk_delete,
        )
        self.spend = to_raw_response_wrapper(
            online_evaluators.spend,
        )


class AsyncOnlineEvaluatorsResourceWithRawResponse:
    def __init__(self, online_evaluators: AsyncOnlineEvaluatorsResource) -> None:
        self._online_evaluators = online_evaluators

        self.create = async_to_raw_response_wrapper(
            online_evaluators.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            online_evaluators.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            online_evaluators.update,
        )
        self.list = async_to_raw_response_wrapper(
            online_evaluators.list,
        )
        self.delete = async_to_raw_response_wrapper(
            online_evaluators.delete,
        )
        self.bulk_delete = async_to_raw_response_wrapper(
            online_evaluators.bulk_delete,
        )
        self.spend = async_to_raw_response_wrapper(
            online_evaluators.spend,
        )


class OnlineEvaluatorsResourceWithStreamingResponse:
    def __init__(self, online_evaluators: OnlineEvaluatorsResource) -> None:
        self._online_evaluators = online_evaluators

        self.create = to_streamed_response_wrapper(
            online_evaluators.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            online_evaluators.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            online_evaluators.update,
        )
        self.list = to_streamed_response_wrapper(
            online_evaluators.list,
        )
        self.delete = to_streamed_response_wrapper(
            online_evaluators.delete,
        )
        self.bulk_delete = to_streamed_response_wrapper(
            online_evaluators.bulk_delete,
        )
        self.spend = to_streamed_response_wrapper(
            online_evaluators.spend,
        )


class AsyncOnlineEvaluatorsResourceWithStreamingResponse:
    def __init__(self, online_evaluators: AsyncOnlineEvaluatorsResource) -> None:
        self._online_evaluators = online_evaluators

        self.create = async_to_streamed_response_wrapper(
            online_evaluators.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            online_evaluators.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            online_evaluators.update,
        )
        self.list = async_to_streamed_response_wrapper(
            online_evaluators.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            online_evaluators.delete,
        )
        self.bulk_delete = async_to_streamed_response_wrapper(
            online_evaluators.bulk_delete,
        )
        self.spend = async_to_streamed_response_wrapper(
            online_evaluators.spend,
        )
