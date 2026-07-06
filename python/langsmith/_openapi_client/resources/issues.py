# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal

import httpx

from ..types import issue_list_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import path_template, maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..pagination import SyncOffsetPaginationIssues, AsyncOffsetPaginationIssues
from ..types.issue import Issue
from .._base_client import AsyncPaginator, make_request_options

__all__ = ["IssuesResource", "AsyncIssuesResource"]


class IssuesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> IssuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return IssuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> IssuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return IssuesResourceWithStreamingResponse(self)

    def retrieve(
        self,
        id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Issue:
        """
        **Beta:** This endpoint is in active development and may change without notice.

        Returns one issue for the authenticated tenant.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not id:
            raise ValueError(f"Expected a non-empty value for `id` but received {id!r}")
        return self._get(
            path_template("/v1/platform/issues/{id}", id=id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Issue,
        )

    def list(
        self,
        *,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        session_id: str | Omit = omit,
        session_name: str | Omit = omit,
        severity: Literal[0, 1, 2, 3] | Omit = omit,
        sort_by: Literal["created_at", "updated_at", "severity"] | Omit = omit,
        status: Literal["open", "completed", "ignored"] | Omit = omit,
        tag: str | Omit = omit,
        updated_at: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationIssues[Issue]:
        """
        **Beta:** This endpoint is in active development and may change without notice.

        Returns issues for the authenticated tenant, optionally filtered by session,
        status, severity, tag, or last modified time.

        Args:
          limit: Page size (positive integer; defaults to 50, capped at 500)

          offset: Page offset (non-negative integer)

          session_id: Filter by session ID (UUID)

          session_name: Filter by session name (exact match)

          severity: Filter by severity

          sort_by: Sort field

          status: Filter by status

          tag: Filter by tag (exact match)

          updated_at: Return only issues updated at or after this RFC3339 timestamp

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v1/platform/issues",
            page=SyncOffsetPaginationIssues[Issue],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                        "session_id": session_id,
                        "session_name": session_name,
                        "severity": severity,
                        "sort_by": sort_by,
                        "status": status,
                        "tag": tag,
                        "updated_at": updated_at,
                    },
                    issue_list_params.IssueListParams,
                ),
            ),
            model=Issue,
        )


class AsyncIssuesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncIssuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#accessing-raw-response-data-eg-headers
        """
        return AsyncIssuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncIssuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langchain-python#with_streaming_response
        """
        return AsyncIssuesResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Issue:
        """
        **Beta:** This endpoint is in active development and may change without notice.

        Returns one issue for the authenticated tenant.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not id:
            raise ValueError(f"Expected a non-empty value for `id` but received {id!r}")
        return await self._get(
            path_template("/v1/platform/issues/{id}", id=id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Issue,
        )

    def list(
        self,
        *,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        session_id: str | Omit = omit,
        session_name: str | Omit = omit,
        severity: Literal[0, 1, 2, 3] | Omit = omit,
        sort_by: Literal["created_at", "updated_at", "severity"] | Omit = omit,
        status: Literal["open", "completed", "ignored"] | Omit = omit,
        tag: str | Omit = omit,
        updated_at: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[Issue, AsyncOffsetPaginationIssues[Issue]]:
        """
        **Beta:** This endpoint is in active development and may change without notice.

        Returns issues for the authenticated tenant, optionally filtered by session,
        status, severity, tag, or last modified time.

        Args:
          limit: Page size (positive integer; defaults to 50, capped at 500)

          offset: Page offset (non-negative integer)

          session_id: Filter by session ID (UUID)

          session_name: Filter by session name (exact match)

          severity: Filter by severity

          sort_by: Sort field

          status: Filter by status

          tag: Filter by tag (exact match)

          updated_at: Return only issues updated at or after this RFC3339 timestamp

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/v1/platform/issues",
            page=AsyncOffsetPaginationIssues[Issue],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                        "session_id": session_id,
                        "session_name": session_name,
                        "severity": severity,
                        "sort_by": sort_by,
                        "status": status,
                        "tag": tag,
                        "updated_at": updated_at,
                    },
                    issue_list_params.IssueListParams,
                ),
            ),
            model=Issue,
        )


class IssuesResourceWithRawResponse:
    def __init__(self, issues: IssuesResource) -> None:
        self._issues = issues

        self.retrieve = to_raw_response_wrapper(
            issues.retrieve,
        )
        self.list = to_raw_response_wrapper(
            issues.list,
        )


class AsyncIssuesResourceWithRawResponse:
    def __init__(self, issues: AsyncIssuesResource) -> None:
        self._issues = issues

        self.retrieve = async_to_raw_response_wrapper(
            issues.retrieve,
        )
        self.list = async_to_raw_response_wrapper(
            issues.list,
        )


class IssuesResourceWithStreamingResponse:
    def __init__(self, issues: IssuesResource) -> None:
        self._issues = issues

        self.retrieve = to_streamed_response_wrapper(
            issues.retrieve,
        )
        self.list = to_streamed_response_wrapper(
            issues.list,
        )


class AsyncIssuesResourceWithStreamingResponse:
    def __init__(self, issues: AsyncIssuesResource) -> None:
        self._issues = issues

        self.retrieve = async_to_streamed_response_wrapper(
            issues.retrieve,
        )
        self.list = async_to_streamed_response_wrapper(
            issues.list,
        )
