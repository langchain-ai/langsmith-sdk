# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal

import httpx

from ...._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ...._utils import maybe_transform, async_maybe_transform
from ...._compat import cached_property
from ...._resource import SyncAPIResource, AsyncAPIResource
from ...._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...._base_client import make_request_options
from ....types.workspaces.secrets import encrypted_retrieve_params
from ....types.workspaces.secrets.encrypted_retrieve_response import EncryptedRetrieveResponse

__all__ = ["EncryptedResource", "AsyncEncryptedResource"]


class EncryptedResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> EncryptedResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return EncryptedResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> EncryptedResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return EncryptedResourceWithStreamingResponse(self)

    def retrieve(
        self,
        *,
        service: Literal["agent_builder", "polly"],
        expand_iam_role: bool | Omit = omit,
        key_names: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EncryptedRetrieveResponse:
        """
        Get encrypted workspace secrets for use with Fleet and external services.

        Args:
          service: Service requesting encrypted secrets

          expand_iam_role: If true, expand AWS_IAM_ROLE_ARN into temporary credentials via STS

          key_names: Optional list of workspace secret keys to return

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/api/v1/workspaces/current/secrets/encrypted",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "service": service,
                        "expand_iam_role": expand_iam_role,
                        "key_names": key_names,
                    },
                    encrypted_retrieve_params.EncryptedRetrieveParams,
                ),
            ),
            cast_to=EncryptedRetrieveResponse,
        )


class AsyncEncryptedResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncEncryptedResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncEncryptedResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncEncryptedResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncEncryptedResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        *,
        service: Literal["agent_builder", "polly"],
        expand_iam_role: bool | Omit = omit,
        key_names: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EncryptedRetrieveResponse:
        """
        Get encrypted workspace secrets for use with Fleet and external services.

        Args:
          service: Service requesting encrypted secrets

          expand_iam_role: If true, expand AWS_IAM_ROLE_ARN into temporary credentials via STS

          key_names: Optional list of workspace secret keys to return

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/api/v1/workspaces/current/secrets/encrypted",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "service": service,
                        "expand_iam_role": expand_iam_role,
                        "key_names": key_names,
                    },
                    encrypted_retrieve_params.EncryptedRetrieveParams,
                ),
            ),
            cast_to=EncryptedRetrieveResponse,
        )


class EncryptedResourceWithRawResponse:
    def __init__(self, encrypted: EncryptedResource) -> None:
        self._encrypted = encrypted

        self.retrieve = to_raw_response_wrapper(
            encrypted.retrieve,
        )


class AsyncEncryptedResourceWithRawResponse:
    def __init__(self, encrypted: AsyncEncryptedResource) -> None:
        self._encrypted = encrypted

        self.retrieve = async_to_raw_response_wrapper(
            encrypted.retrieve,
        )


class EncryptedResourceWithStreamingResponse:
    def __init__(self, encrypted: EncryptedResource) -> None:
        self._encrypted = encrypted

        self.retrieve = to_streamed_response_wrapper(
            encrypted.retrieve,
        )


class AsyncEncryptedResourceWithStreamingResponse:
    def __init__(self, encrypted: AsyncEncryptedResource) -> None:
        self._encrypted = encrypted

        self.retrieve = async_to_streamed_response_wrapper(
            encrypted.retrieve,
        )
