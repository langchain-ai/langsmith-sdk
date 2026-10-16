# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Optional
from typing_extensions import Literal

from ..types import prompt_webhook_test_params, prompt_webhook_create_params, prompt_webhook_update_params
from .._httpx import httpx
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
from .._base_client import make_request_options
from ..types.prompt_webhook import PromptWebhook
from ..types.prompt_webhook_list_response import PromptWebhookListResponse
from ..types.prompt_webhook_test_response import PromptWebhookTestResponse

__all__ = ["PromptWebhooksResource", "AsyncPromptWebhooksResource"]


class PromptWebhooksResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> PromptWebhooksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return PromptWebhooksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> PromptWebhooksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return PromptWebhooksResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        url: str,
        id: Optional[str] | Omit = omit,
        exclude_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        headers: Optional[Dict[str, object]] | Omit = omit,
        include_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        triggers: List[Literal["commit", "tag:create", "tag:update"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Create a new prompt webhook.

        LangSmith sends a POST request to the webhook URL for each event listed in
        triggers on the prompts it matches. A workspace can have one prompt webhook
        unless its limit was raised; creating one past the limit returns 400.

        Args:
          url: URL that receives a POST request with the prompt event payload.

          id: ID to assign to the webhook. Generated when omitted.

          exclude_prompts: IDs of prompts whose events never fire the webhook.

          headers: HTTP headers sent with each request, for example an Authorization header. Values
              are stored encrypted and are masked in responses to callers who cannot update
              prompts.

          include_prompts: IDs of the prompts whose events fire the webhook. When empty, events from every
              prompt in the workspace fire it.

          triggers: Events that fire the webhook: commit (a new prompt commit), tag:create, and
              tag:update. A webhook with no triggers never fires.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/prompt-webhooks",
            body=maybe_transform(
                {
                    "url": url,
                    "id": id,
                    "exclude_prompts": exclude_prompts,
                    "headers": headers,
                    "include_prompts": include_prompts,
                    "triggers": triggers,
                },
                prompt_webhook_create_params.PromptWebhookCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    def retrieve(
        self,
        webhook_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Get a specific prompt webhook.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        return self._get(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    def update(
        self,
        webhook_id: str,
        *,
        exclude_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        headers: Optional[Dict[str, object]] | Omit = omit,
        include_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        triggers: Optional[List[Literal["commit", "tag:create", "tag:update"]]] | Omit = omit,
        url: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Update a specific prompt webhook.

        Omitted fields keep their current values; list fields and headers that are set
        replace the stored values.

        Args:
          exclude_prompts: IDs of prompts whose events never fire the webhook, replacing the current list.
              Omit to keep it.

          headers: HTTP headers sent with each request, replacing all current headers. Omit to keep
              them. Masked values (**\\**\\**\\**\\****) from a read are rejected.

          include_prompts: IDs of the prompts whose events fire the webhook, replacing the current list.
              Omit to keep it.

          triggers: Events that fire the webhook (commit, tag:create, tag:update), replacing the
              current list. Omit to keep it.

          url: URL that receives the POST requests. Omit to keep the current URL.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        return self._patch(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            body=maybe_transform(
                {
                    "exclude_prompts": exclude_prompts,
                    "headers": headers,
                    "include_prompts": include_prompts,
                    "triggers": triggers,
                    "url": url,
                },
                prompt_webhook_update_params.PromptWebhookUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    def list(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhookListResponse:
        """List all prompt webhooks for the current tenant."""
        return self._get(
            "/api/v1/prompt-webhooks",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhookListResponse,
        )

    def delete(
        self,
        webhook_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Delete a specific prompt webhook.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return self._delete(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    def test(
        self,
        *,
        payload: prompt_webhook_test_params.Payload,
        webhook: prompt_webhook_test_params.Webhook,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhookTestResponse:
        """
        Test a specific prompt webhook.

        Sends the sample payload to the webhook configuration in the request body
        without saving it, but only if the webhook's triggers include the payload's
        event and its prompt filters match the payload's prompt. Otherwise nothing is
        sent. Fails if the destination does not accept the payload.

        Args:
          webhook: Base schema for prompt webhooks.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/prompt-webhooks/test",
            body=maybe_transform(
                {
                    "payload": payload,
                    "webhook": webhook,
                },
                prompt_webhook_test_params.PromptWebhookTestParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhookTestResponse,
        )


class AsyncPromptWebhooksResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncPromptWebhooksResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#accessing-raw-response-data-eg-headers
        """
        return AsyncPromptWebhooksResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncPromptWebhooksResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/langchain-ai/langsmith-python#with_streaming_response
        """
        return AsyncPromptWebhooksResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        url: str,
        id: Optional[str] | Omit = omit,
        exclude_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        headers: Optional[Dict[str, object]] | Omit = omit,
        include_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        triggers: List[Literal["commit", "tag:create", "tag:update"]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Create a new prompt webhook.

        LangSmith sends a POST request to the webhook URL for each event listed in
        triggers on the prompts it matches. A workspace can have one prompt webhook
        unless its limit was raised; creating one past the limit returns 400.

        Args:
          url: URL that receives a POST request with the prompt event payload.

          id: ID to assign to the webhook. Generated when omitted.

          exclude_prompts: IDs of prompts whose events never fire the webhook.

          headers: HTTP headers sent with each request, for example an Authorization header. Values
              are stored encrypted and are masked in responses to callers who cannot update
              prompts.

          include_prompts: IDs of the prompts whose events fire the webhook. When empty, events from every
              prompt in the workspace fire it.

          triggers: Events that fire the webhook: commit (a new prompt commit), tag:create, and
              tag:update. A webhook with no triggers never fires.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/prompt-webhooks",
            body=await async_maybe_transform(
                {
                    "url": url,
                    "id": id,
                    "exclude_prompts": exclude_prompts,
                    "headers": headers,
                    "include_prompts": include_prompts,
                    "triggers": triggers,
                },
                prompt_webhook_create_params.PromptWebhookCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    async def retrieve(
        self,
        webhook_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Get a specific prompt webhook.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        return await self._get(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    async def update(
        self,
        webhook_id: str,
        *,
        exclude_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        headers: Optional[Dict[str, object]] | Omit = omit,
        include_prompts: Optional[SequenceNotStr[str]] | Omit = omit,
        triggers: Optional[List[Literal["commit", "tag:create", "tag:update"]]] | Omit = omit,
        url: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhook:
        """
        Update a specific prompt webhook.

        Omitted fields keep their current values; list fields and headers that are set
        replace the stored values.

        Args:
          exclude_prompts: IDs of prompts whose events never fire the webhook, replacing the current list.
              Omit to keep it.

          headers: HTTP headers sent with each request, replacing all current headers. Omit to keep
              them. Masked values (**\\**\\**\\**\\****) from a read are rejected.

          include_prompts: IDs of the prompts whose events fire the webhook, replacing the current list.
              Omit to keep it.

          triggers: Events that fire the webhook (commit, tag:create, tag:update), replacing the
              current list. Omit to keep it.

          url: URL that receives the POST requests. Omit to keep the current URL.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        return await self._patch(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            body=await async_maybe_transform(
                {
                    "exclude_prompts": exclude_prompts,
                    "headers": headers,
                    "include_prompts": include_prompts,
                    "triggers": triggers,
                    "url": url,
                },
                prompt_webhook_update_params.PromptWebhookUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhook,
        )

    async def list(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhookListResponse:
        """List all prompt webhooks for the current tenant."""
        return await self._get(
            "/api/v1/prompt-webhooks",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhookListResponse,
        )

    async def delete(
        self,
        webhook_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> None:
        """
        Delete a specific prompt webhook.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not webhook_id:
            raise ValueError(f"Expected a non-empty value for `webhook_id` but received {webhook_id!r}")
        extra_headers = {"Accept": "*/*", **(extra_headers or {})}
        return await self._delete(
            path_template("/api/v1/prompt-webhooks/{webhook_id}", webhook_id=webhook_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=NoneType,
        )

    async def test(
        self,
        *,
        payload: prompt_webhook_test_params.Payload,
        webhook: prompt_webhook_test_params.Webhook,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> PromptWebhookTestResponse:
        """
        Test a specific prompt webhook.

        Sends the sample payload to the webhook configuration in the request body
        without saving it, but only if the webhook's triggers include the payload's
        event and its prompt filters match the payload's prompt. Otherwise nothing is
        sent. Fails if the destination does not accept the payload.

        Args:
          webhook: Base schema for prompt webhooks.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/prompt-webhooks/test",
            body=await async_maybe_transform(
                {
                    "payload": payload,
                    "webhook": webhook,
                },
                prompt_webhook_test_params.PromptWebhookTestParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=PromptWebhookTestResponse,
        )


class PromptWebhooksResourceWithRawResponse:
    def __init__(self, prompt_webhooks: PromptWebhooksResource) -> None:
        self._prompt_webhooks = prompt_webhooks

        self.create = to_raw_response_wrapper(
            prompt_webhooks.create,
        )
        self.retrieve = to_raw_response_wrapper(
            prompt_webhooks.retrieve,
        )
        self.update = to_raw_response_wrapper(
            prompt_webhooks.update,
        )
        self.list = to_raw_response_wrapper(
            prompt_webhooks.list,
        )
        self.delete = to_raw_response_wrapper(
            prompt_webhooks.delete,
        )
        self.test = to_raw_response_wrapper(
            prompt_webhooks.test,
        )


class AsyncPromptWebhooksResourceWithRawResponse:
    def __init__(self, prompt_webhooks: AsyncPromptWebhooksResource) -> None:
        self._prompt_webhooks = prompt_webhooks

        self.create = async_to_raw_response_wrapper(
            prompt_webhooks.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            prompt_webhooks.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            prompt_webhooks.update,
        )
        self.list = async_to_raw_response_wrapper(
            prompt_webhooks.list,
        )
        self.delete = async_to_raw_response_wrapper(
            prompt_webhooks.delete,
        )
        self.test = async_to_raw_response_wrapper(
            prompt_webhooks.test,
        )


class PromptWebhooksResourceWithStreamingResponse:
    def __init__(self, prompt_webhooks: PromptWebhooksResource) -> None:
        self._prompt_webhooks = prompt_webhooks

        self.create = to_streamed_response_wrapper(
            prompt_webhooks.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            prompt_webhooks.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            prompt_webhooks.update,
        )
        self.list = to_streamed_response_wrapper(
            prompt_webhooks.list,
        )
        self.delete = to_streamed_response_wrapper(
            prompt_webhooks.delete,
        )
        self.test = to_streamed_response_wrapper(
            prompt_webhooks.test,
        )


class AsyncPromptWebhooksResourceWithStreamingResponse:
    def __init__(self, prompt_webhooks: AsyncPromptWebhooksResource) -> None:
        self._prompt_webhooks = prompt_webhooks

        self.create = async_to_streamed_response_wrapper(
            prompt_webhooks.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            prompt_webhooks.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            prompt_webhooks.update,
        )
        self.list = async_to_streamed_response_wrapper(
            prompt_webhooks.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            prompt_webhooks.delete,
        )
        self.test = async_to_streamed_response_wrapper(
            prompt_webhooks.test,
        )
