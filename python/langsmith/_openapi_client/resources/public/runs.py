# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union
from datetime import datetime
from typing_extensions import Literal

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, strip_not_given, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ...types.run import Run
from ..._base_client import make_request_options
from ...types.public import run_query_params, run_retrieve_params
from ...types.public.run_query_response import RunQueryResponse

__all__ = ["RunsResource", "AsyncRunsResource"]


class RunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return RunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return RunsResourceWithStreamingResponse(self)

    def retrieve(
        self,
        run_id: str,
        *,
        share_token: str,
        selects: SequenceNotStr[str],
        start_time: Union[str, datetime],
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Run:
        """
        **Alpha:** The request and response contract may change; Returns one run within
        the trace identified by the share token. The request supplies only the run ID
        and that run's exact start_time coordinate.

        Args:
          selects: repeatable public run fields to include

          start_time: Run start_time coordinate (RFC3339)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._get(
            path_template("/v2/public/{share_token}/run/{run_id}", share_token=share_token, run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "selects": selects,
                        "start_time": start_time,
                    },
                    run_retrieve_params.RunRetrieveParams,
                ),
            ),
            cast_to=Run,
        )

    def query(
        self,
        share_token: str,
        *,
        selects: List[
            Literal[
                "ID",
                "NAME",
                "RUN_TYPE",
                "STATUS",
                "START_TIME",
                "END_TIME",
                "LATENCY_SECONDS",
                "FIRST_TOKEN_TIME",
                "ERROR",
                "ERROR_PREVIEW",
                "EXTRA",
                "METADATA",
                "INPUTS_PREVIEW",
                "OUTPUTS_PREVIEW",
                "PARENT_RUN_ID",
                "PARENT_RUN_IDS",
                "PROJECT_ID",
                "TRACE_ID",
                "THREAD_ID",
                "DOTTED_ORDER",
                "IS_ROOT",
                "REFERENCE_DATASET_ID",
                "TOTAL_TOKENS",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_COST",
                "PROMPT_COST",
                "COMPLETION_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "PRICE_MODEL_ID",
                "TAGS",
                "THREAD_EVALUATION_TIME",
                "FEEDBACK_STATS",
            ]
        ]
        | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunQueryResponse:
        """
        **Alpha:** The request and response contract may change; Returns all runs within
        the trace identified by the share token. The share token supplies the tenant,
        project, and trace scope.

        Args:
          selects: `selects` lists which public run properties to include on each returned run.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return self._post(
            path_template("/v2/public/{share_token}/runs/v2/query", share_token=share_token),
            body=maybe_transform({"selects": selects}, run_query_params.RunQueryParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RunQueryResponse,
        )


class AsyncRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.
        """
        return AsyncRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.
        """
        return AsyncRunsResourceWithStreamingResponse(self)

    async def retrieve(
        self,
        run_id: str,
        *,
        share_token: str,
        selects: SequenceNotStr[str],
        start_time: Union[str, datetime],
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Run:
        """
        **Alpha:** The request and response contract may change; Returns one run within
        the trace identified by the share token. The request supplies only the run ID
        and that run's exact start_time coordinate.

        Args:
          selects: repeatable public run fields to include

          start_time: Run start_time coordinate (RFC3339)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        if not run_id:
            raise ValueError(f"Expected a non-empty value for `run_id` but received {run_id!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return await self._get(
            path_template("/v2/public/{share_token}/run/{run_id}", share_token=share_token, run_id=run_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "selects": selects,
                        "start_time": start_time,
                    },
                    run_retrieve_params.RunRetrieveParams,
                ),
            ),
            cast_to=Run,
        )

    async def query(
        self,
        share_token: str,
        *,
        selects: List[
            Literal[
                "ID",
                "NAME",
                "RUN_TYPE",
                "STATUS",
                "START_TIME",
                "END_TIME",
                "LATENCY_SECONDS",
                "FIRST_TOKEN_TIME",
                "ERROR",
                "ERROR_PREVIEW",
                "EXTRA",
                "METADATA",
                "INPUTS_PREVIEW",
                "OUTPUTS_PREVIEW",
                "PARENT_RUN_ID",
                "PARENT_RUN_IDS",
                "PROJECT_ID",
                "TRACE_ID",
                "THREAD_ID",
                "DOTTED_ORDER",
                "IS_ROOT",
                "REFERENCE_DATASET_ID",
                "TOTAL_TOKENS",
                "PROMPT_TOKENS",
                "COMPLETION_TOKENS",
                "TOTAL_COST",
                "PROMPT_COST",
                "COMPLETION_COST",
                "PROMPT_TOKEN_DETAILS",
                "COMPLETION_TOKEN_DETAILS",
                "PROMPT_COST_DETAILS",
                "COMPLETION_COST_DETAILS",
                "PRICE_MODEL_ID",
                "TAGS",
                "THREAD_EVALUATION_TIME",
                "FEEDBACK_STATS",
            ]
        ]
        | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RunQueryResponse:
        """
        **Alpha:** The request and response contract may change; Returns all runs within
        the trace identified by the share token. The share token supplies the tenant,
        project, and trace scope.

        Args:
          selects: `selects` lists which public run properties to include on each returned run.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not share_token:
            raise ValueError(f"Expected a non-empty value for `share_token` but received {share_token!r}")
        extra_headers = {**strip_not_given({"Accept": accept}), **(extra_headers or {})}
        return await self._post(
            path_template("/v2/public/{share_token}/runs/v2/query", share_token=share_token),
            body=await async_maybe_transform({"selects": selects}, run_query_params.RunQueryParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RunQueryResponse,
        )


class RunsResourceWithRawResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.retrieve = to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = to_raw_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithRawResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.retrieve = async_to_raw_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_raw_response_wrapper(
            runs.query,
        )


class RunsResourceWithStreamingResponse:
    def __init__(self, runs: RunsResource) -> None:
        self._runs = runs

        self.retrieve = to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = to_streamed_response_wrapper(
            runs.query,
        )


class AsyncRunsResourceWithStreamingResponse:
    def __init__(self, runs: AsyncRunsResource) -> None:
        self._runs = runs

        self.retrieve = async_to_streamed_response_wrapper(
            runs.retrieve,
        )
        self.query = async_to_streamed_response_wrapper(
            runs.query,
        )
