# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal

import httpx

from .tags import (
    TagsResource,
    AsyncTagsResource,
    TagsResourceWithRawResponse,
    AsyncTagsResourceWithRawResponse,
    TagsResourceWithStreamingResponse,
    AsyncTagsResourceWithStreamingResponse,
)
from ...types import repo_list_params, repo_create_params, repo_update_params
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
from ...pagination import SyncOffsetPaginationRepos, AsyncOffsetPaginationRepos
from ..._base_client import AsyncPaginator, make_request_options
from ...types.get_repo_response import GetRepoResponse
from ...types.repo_with_lookups import RepoWithLookups
from ...types.create_repo_response import CreateRepoResponse

__all__ = ["ReposResource", "AsyncReposResource"]


class ReposResource(SyncAPIResource):
    @cached_property
    def tags(self) -> TagsResource:
        return TagsResource(self._client)

    @cached_property
    def with_raw_response(self) -> ReposResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ReposResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ReposResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ReposResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        is_public: bool,
        repo_handle: str,
        description: Optional[str] | Omit = omit,
        readme: Optional[str] | Omit = omit,
        repo_type: Literal["prompt", "file", "agent", "skill"] | Omit = omit,
        restricted_mode: Optional[bool] | Omit = omit,
        source: Optional[Literal["internal", "external"]] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateRepoResponse:
        """
        Create a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/repos",
            body=maybe_transform(
                {
                    "is_public": is_public,
                    "repo_handle": repo_handle,
                    "description": description,
                    "readme": readme,
                    "repo_type": repo_type,
                    "restricted_mode": restricted_mode,
                    "source": source,
                    "tags": tags,
                },
                repo_create_params.RepoCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateRepoResponse,
        )

    def retrieve(
        self,
        repo: str,
        *,
        owner: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GetRepoResponse:
        """
        Get a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return self._get(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=GetRepoResponse,
        )

    def update(
        self,
        repo: str,
        *,
        owner: str,
        description: Optional[str] | Omit = omit,
        is_archived: Optional[bool] | Omit = omit,
        is_public: Optional[bool] | Omit = omit,
        readme: Optional[str] | Omit = omit,
        restricted_mode: Optional[bool] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateRepoResponse:
        """
        Update a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return self._patch(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            body=maybe_transform(
                {
                    "description": description,
                    "is_archived": is_archived,
                    "is_public": is_public,
                    "readme": readme,
                    "restricted_mode": restricted_mode,
                    "tags": tags,
                },
                repo_update_params.RepoUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateRepoResponse,
        )

    def list(
        self,
        *,
        has_commits: Optional[bool] | Omit = omit,
        is_archived: Optional[Literal["true", "allow", "false"]] | Omit = omit,
        is_public: Optional[Literal["true", "false"]] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[str] | Omit = omit,
        repo_type: Optional[Literal["prompt", "file", "agent", "skill"]] | Omit = omit,
        repo_types: Optional[List[Literal["prompt", "file", "agent", "skill"]]] | Omit = omit,
        sort_direction: Optional[Literal["asc", "desc"]] | Omit = omit,
        sort_field: Optional[Literal["num_likes", "num_downloads", "num_views", "updated_at", "relevance"]]
        | Omit = omit,
        source: Optional[Literal["internal", "external"]] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        tenant_handle: Optional[str] | Omit = omit,
        tenant_id: Optional[str] | Omit = omit,
        upstream_repo_handle: Optional[str] | Omit = omit,
        upstream_repo_owner: Optional[str] | Omit = omit,
        with_latest_manifest: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationRepos[RepoWithLookups]:
        """
        Get all repos.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/repos",
            page=SyncOffsetPaginationRepos[RepoWithLookups],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "has_commits": has_commits,
                        "is_archived": is_archived,
                        "is_public": is_public,
                        "limit": limit,
                        "offset": offset,
                        "query": query,
                        "repo_type": repo_type,
                        "repo_types": repo_types,
                        "sort_direction": sort_direction,
                        "sort_field": sort_field,
                        "source": source,
                        "tag_value_id": tag_value_id,
                        "tags": tags,
                        "tenant_handle": tenant_handle,
                        "tenant_id": tenant_id,
                        "upstream_repo_handle": upstream_repo_handle,
                        "upstream_repo_owner": upstream_repo_owner,
                        "with_latest_manifest": with_latest_manifest,
                    },
                    repo_list_params.RepoListParams,
                ),
            ),
            model=RepoWithLookups,
        )

    def delete(
        self,
        repo: str,
        *,
        owner: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return self._delete(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncReposResource(AsyncAPIResource):
    @cached_property
    def tags(self) -> AsyncTagsResource:
        return AsyncTagsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncReposResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncReposResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncReposResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncReposResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        is_public: bool,
        repo_handle: str,
        description: Optional[str] | Omit = omit,
        readme: Optional[str] | Omit = omit,
        repo_type: Literal["prompt", "file", "agent", "skill"] | Omit = omit,
        restricted_mode: Optional[bool] | Omit = omit,
        source: Optional[Literal["internal", "external"]] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateRepoResponse:
        """
        Create a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/repos",
            body=await async_maybe_transform(
                {
                    "is_public": is_public,
                    "repo_handle": repo_handle,
                    "description": description,
                    "readme": readme,
                    "repo_type": repo_type,
                    "restricted_mode": restricted_mode,
                    "source": source,
                    "tags": tags,
                },
                repo_create_params.RepoCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateRepoResponse,
        )

    async def retrieve(
        self,
        repo: str,
        *,
        owner: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> GetRepoResponse:
        """
        Get a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return await self._get(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=GetRepoResponse,
        )

    async def update(
        self,
        repo: str,
        *,
        owner: str,
        description: Optional[str] | Omit = omit,
        is_archived: Optional[bool] | Omit = omit,
        is_public: Optional[bool] | Omit = omit,
        readme: Optional[str] | Omit = omit,
        restricted_mode: Optional[bool] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CreateRepoResponse:
        """
        Update a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return await self._patch(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            body=await async_maybe_transform(
                {
                    "description": description,
                    "is_archived": is_archived,
                    "is_public": is_public,
                    "readme": readme,
                    "restricted_mode": restricted_mode,
                    "tags": tags,
                },
                repo_update_params.RepoUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CreateRepoResponse,
        )

    def list(
        self,
        *,
        has_commits: Optional[bool] | Omit = omit,
        is_archived: Optional[Literal["true", "allow", "false"]] | Omit = omit,
        is_public: Optional[Literal["true", "false"]] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[str] | Omit = omit,
        repo_type: Optional[Literal["prompt", "file", "agent", "skill"]] | Omit = omit,
        repo_types: Optional[List[Literal["prompt", "file", "agent", "skill"]]] | Omit = omit,
        sort_direction: Optional[Literal["asc", "desc"]] | Omit = omit,
        sort_field: Optional[Literal["num_likes", "num_downloads", "num_views", "updated_at", "relevance"]]
        | Omit = omit,
        source: Optional[Literal["internal", "external"]] | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        tags: Optional[SequenceNotStr[str]] | Omit = omit,
        tenant_handle: Optional[str] | Omit = omit,
        tenant_id: Optional[str] | Omit = omit,
        upstream_repo_handle: Optional[str] | Omit = omit,
        upstream_repo_owner: Optional[str] | Omit = omit,
        with_latest_manifest: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[RepoWithLookups, AsyncOffsetPaginationRepos[RepoWithLookups]]:
        """
        Get all repos.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/repos",
            page=AsyncOffsetPaginationRepos[RepoWithLookups],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "has_commits": has_commits,
                        "is_archived": is_archived,
                        "is_public": is_public,
                        "limit": limit,
                        "offset": offset,
                        "query": query,
                        "repo_type": repo_type,
                        "repo_types": repo_types,
                        "sort_direction": sort_direction,
                        "sort_field": sort_field,
                        "source": source,
                        "tag_value_id": tag_value_id,
                        "tags": tags,
                        "tenant_handle": tenant_handle,
                        "tenant_id": tenant_id,
                        "upstream_repo_handle": upstream_repo_handle,
                        "upstream_repo_owner": upstream_repo_owner,
                        "with_latest_manifest": with_latest_manifest,
                    },
                    repo_list_params.RepoListParams,
                ),
            ),
            model=RepoWithLookups,
        )

    async def delete(
        self,
        repo: str,
        *,
        owner: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a repo.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not owner:
            raise ValueError(f"Expected a non-empty value for `owner` but received {owner!r}")
        if not repo:
            raise ValueError(f"Expected a non-empty value for `repo` but received {repo!r}")
        return await self._delete(
            path_template("/api/v1/repos/{owner}/{repo}", owner=owner, repo=repo),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class ReposResourceWithRawResponse:
    def __init__(self, repos: ReposResource) -> None:
        self._repos = repos

        self.create = to_raw_response_wrapper(
            repos.create,
        )
        self.retrieve = to_raw_response_wrapper(
            repos.retrieve,
        )
        self.update = to_raw_response_wrapper(
            repos.update,
        )
        self.list = to_raw_response_wrapper(
            repos.list,
        )
        self.delete = to_raw_response_wrapper(
            repos.delete,
        )

    @cached_property
    def tags(self) -> TagsResourceWithRawResponse:
        return TagsResourceWithRawResponse(self._repos.tags)


class AsyncReposResourceWithRawResponse:
    def __init__(self, repos: AsyncReposResource) -> None:
        self._repos = repos

        self.create = async_to_raw_response_wrapper(
            repos.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            repos.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            repos.update,
        )
        self.list = async_to_raw_response_wrapper(
            repos.list,
        )
        self.delete = async_to_raw_response_wrapper(
            repos.delete,
        )

    @cached_property
    def tags(self) -> AsyncTagsResourceWithRawResponse:
        return AsyncTagsResourceWithRawResponse(self._repos.tags)


class ReposResourceWithStreamingResponse:
    def __init__(self, repos: ReposResource) -> None:
        self._repos = repos

        self.create = to_streamed_response_wrapper(
            repos.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            repos.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            repos.update,
        )
        self.list = to_streamed_response_wrapper(
            repos.list,
        )
        self.delete = to_streamed_response_wrapper(
            repos.delete,
        )

    @cached_property
    def tags(self) -> TagsResourceWithStreamingResponse:
        return TagsResourceWithStreamingResponse(self._repos.tags)


class AsyncReposResourceWithStreamingResponse:
    def __init__(self, repos: AsyncReposResource) -> None:
        self._repos = repos

        self.create = async_to_streamed_response_wrapper(
            repos.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            repos.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            repos.update,
        )
        self.list = async_to_streamed_response_wrapper(
            repos.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            repos.delete,
        )

    @cached_property
    def tags(self) -> AsyncTagsResourceWithStreamingResponse:
        return AsyncTagsResourceWithStreamingResponse(self._repos.tags)
