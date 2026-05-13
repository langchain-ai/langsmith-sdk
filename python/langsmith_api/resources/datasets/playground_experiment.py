# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.datasets import (
    RunnerContextEnum,
    playground_experiment_batch_params,
    playground_experiment_stream_params,
)
from ...types.datasets.runner_context_enum import RunnerContextEnum
from ...types.datasets.runnable_config_param import RunnableConfigParam

__all__ = ["PlaygroundExperimentResource", "AsyncPlaygroundExperimentResource"]


class PlaygroundExperimentResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> PlaygroundExperimentResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return PlaygroundExperimentResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> PlaygroundExperimentResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return PlaygroundExperimentResourceWithStreamingResponse(self)

    def batch(
        self,
        *,
        dataset_id: str,
        manifest: object,
        options: RunnableConfigParam,
        project_name: str,
        secrets: Dict[str, str],
        batch_size: Optional[int] | Omit = omit,
        commit: Optional[str] | Omit = omit,
        dataset_splits: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluator_rules: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        owner: Optional[str] | Omit = omit,
        parallel_tool_calls: Optional[bool] | Omit = omit,
        repetitions: int | Omit = omit,
        repo_handle: Optional[str] | Omit = omit,
        repo_id: Optional[str] | Omit = omit,
        requests_per_second: Optional[int] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        runner_context: Optional[RunnerContextEnum] | Omit = omit,
        tool_choice: Optional[str] | Omit = omit,
        tools: Optional[Iterable[object]] | Omit = omit,
        use_or_fallback_to_workspace_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Dataset Handler

        Args:
          options: Configuration for a `Runnable`.

              !!! note Custom values

                  The `TypedDict` has `total=False` set intentionally to:

                  - Allow partial configs to be created and merged together via `merge_configs`
                  - Support config propagation from parent to child runnables via
                      `var_child_runnable_config` (a `ContextVar` that automatically passes
                      config down the call stack without explicit parameter passing), where
                      configs are merged rather than replaced

                  !!! example

                      ```python
                      # Parent sets tags
                      chain.invoke(input, config={"tags": ["parent"]})
                      # Child automatically inherits and can add:
                      # ensure_config({"tags": ["child"]}) -> {"tags": ["parent", "child"]}
                      ```

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/datasets/playground_experiment/batch",
            body=maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "manifest": manifest,
                    "options": options,
                    "project_name": project_name,
                    "secrets": secrets,
                    "batch_size": batch_size,
                    "commit": commit,
                    "dataset_splits": dataset_splits,
                    "evaluator_rules": evaluator_rules,
                    "metadata": metadata,
                    "owner": owner,
                    "parallel_tool_calls": parallel_tool_calls,
                    "repetitions": repetitions,
                    "repo_handle": repo_handle,
                    "repo_id": repo_id,
                    "requests_per_second": requests_per_second,
                    "run_id": run_id,
                    "runner_context": runner_context,
                    "tool_choice": tool_choice,
                    "tools": tools,
                    "use_or_fallback_to_workspace_secrets": use_or_fallback_to_workspace_secrets,
                },
                playground_experiment_batch_params.PlaygroundExperimentBatchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def stream(
        self,
        *,
        dataset_id: str,
        manifest: object,
        options: RunnableConfigParam,
        project_name: str,
        secrets: Dict[str, str],
        commit: Optional[str] | Omit = omit,
        dataset_splits: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluator_rules: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        owner: Optional[str] | Omit = omit,
        parallel_tool_calls: Optional[bool] | Omit = omit,
        repetitions: int | Omit = omit,
        repo_handle: Optional[str] | Omit = omit,
        repo_id: Optional[str] | Omit = omit,
        requests_per_second: Optional[int] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        runner_context: Optional[RunnerContextEnum] | Omit = omit,
        tool_choice: Optional[str] | Omit = omit,
        tools: Optional[Iterable[object]] | Omit = omit,
        use_or_fallback_to_workspace_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Stream Dataset Handler

        Args:
          options: Configuration for a `Runnable`.

              !!! note Custom values

                  The `TypedDict` has `total=False` set intentionally to:

                  - Allow partial configs to be created and merged together via `merge_configs`
                  - Support config propagation from parent to child runnables via
                      `var_child_runnable_config` (a `ContextVar` that automatically passes
                      config down the call stack without explicit parameter passing), where
                      configs are merged rather than replaced

                  !!! example

                      ```python
                      # Parent sets tags
                      chain.invoke(input, config={"tags": ["parent"]})
                      # Child automatically inherits and can add:
                      # ensure_config({"tags": ["child"]}) -> {"tags": ["parent", "child"]}
                      ```

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/datasets/playground_experiment/stream",
            body=maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "manifest": manifest,
                    "options": options,
                    "project_name": project_name,
                    "secrets": secrets,
                    "commit": commit,
                    "dataset_splits": dataset_splits,
                    "evaluator_rules": evaluator_rules,
                    "metadata": metadata,
                    "owner": owner,
                    "parallel_tool_calls": parallel_tool_calls,
                    "repetitions": repetitions,
                    "repo_handle": repo_handle,
                    "repo_id": repo_id,
                    "requests_per_second": requests_per_second,
                    "run_id": run_id,
                    "runner_context": runner_context,
                    "tool_choice": tool_choice,
                    "tools": tools,
                    "use_or_fallback_to_workspace_secrets": use_or_fallback_to_workspace_secrets,
                },
                playground_experiment_stream_params.PlaygroundExperimentStreamParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncPlaygroundExperimentResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncPlaygroundExperimentResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncPlaygroundExperimentResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncPlaygroundExperimentResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncPlaygroundExperimentResourceWithStreamingResponse(self)

    async def batch(
        self,
        *,
        dataset_id: str,
        manifest: object,
        options: RunnableConfigParam,
        project_name: str,
        secrets: Dict[str, str],
        batch_size: Optional[int] | Omit = omit,
        commit: Optional[str] | Omit = omit,
        dataset_splits: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluator_rules: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        owner: Optional[str] | Omit = omit,
        parallel_tool_calls: Optional[bool] | Omit = omit,
        repetitions: int | Omit = omit,
        repo_handle: Optional[str] | Omit = omit,
        repo_id: Optional[str] | Omit = omit,
        requests_per_second: Optional[int] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        runner_context: Optional[RunnerContextEnum] | Omit = omit,
        tool_choice: Optional[str] | Omit = omit,
        tools: Optional[Iterable[object]] | Omit = omit,
        use_or_fallback_to_workspace_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Dataset Handler

        Args:
          options: Configuration for a `Runnable`.

              !!! note Custom values

                  The `TypedDict` has `total=False` set intentionally to:

                  - Allow partial configs to be created and merged together via `merge_configs`
                  - Support config propagation from parent to child runnables via
                      `var_child_runnable_config` (a `ContextVar` that automatically passes
                      config down the call stack without explicit parameter passing), where
                      configs are merged rather than replaced

                  !!! example

                      ```python
                      # Parent sets tags
                      chain.invoke(input, config={"tags": ["parent"]})
                      # Child automatically inherits and can add:
                      # ensure_config({"tags": ["child"]}) -> {"tags": ["parent", "child"]}
                      ```

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/datasets/playground_experiment/batch",
            body=await async_maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "manifest": manifest,
                    "options": options,
                    "project_name": project_name,
                    "secrets": secrets,
                    "batch_size": batch_size,
                    "commit": commit,
                    "dataset_splits": dataset_splits,
                    "evaluator_rules": evaluator_rules,
                    "metadata": metadata,
                    "owner": owner,
                    "parallel_tool_calls": parallel_tool_calls,
                    "repetitions": repetitions,
                    "repo_handle": repo_handle,
                    "repo_id": repo_id,
                    "requests_per_second": requests_per_second,
                    "run_id": run_id,
                    "runner_context": runner_context,
                    "tool_choice": tool_choice,
                    "tools": tools,
                    "use_or_fallback_to_workspace_secrets": use_or_fallback_to_workspace_secrets,
                },
                playground_experiment_batch_params.PlaygroundExperimentBatchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def stream(
        self,
        *,
        dataset_id: str,
        manifest: object,
        options: RunnableConfigParam,
        project_name: str,
        secrets: Dict[str, str],
        commit: Optional[str] | Omit = omit,
        dataset_splits: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluator_rules: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        owner: Optional[str] | Omit = omit,
        parallel_tool_calls: Optional[bool] | Omit = omit,
        repetitions: int | Omit = omit,
        repo_handle: Optional[str] | Omit = omit,
        repo_id: Optional[str] | Omit = omit,
        requests_per_second: Optional[int] | Omit = omit,
        run_id: Optional[str] | Omit = omit,
        runner_context: Optional[RunnerContextEnum] | Omit = omit,
        tool_choice: Optional[str] | Omit = omit,
        tools: Optional[Iterable[object]] | Omit = omit,
        use_or_fallback_to_workspace_secrets: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Stream Dataset Handler

        Args:
          options: Configuration for a `Runnable`.

              !!! note Custom values

                  The `TypedDict` has `total=False` set intentionally to:

                  - Allow partial configs to be created and merged together via `merge_configs`
                  - Support config propagation from parent to child runnables via
                      `var_child_runnable_config` (a `ContextVar` that automatically passes
                      config down the call stack without explicit parameter passing), where
                      configs are merged rather than replaced

                  !!! example

                      ```python
                      # Parent sets tags
                      chain.invoke(input, config={"tags": ["parent"]})
                      # Child automatically inherits and can add:
                      # ensure_config({"tags": ["child"]}) -> {"tags": ["parent", "child"]}
                      ```

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/datasets/playground_experiment/stream",
            body=await async_maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "manifest": manifest,
                    "options": options,
                    "project_name": project_name,
                    "secrets": secrets,
                    "commit": commit,
                    "dataset_splits": dataset_splits,
                    "evaluator_rules": evaluator_rules,
                    "metadata": metadata,
                    "owner": owner,
                    "parallel_tool_calls": parallel_tool_calls,
                    "repetitions": repetitions,
                    "repo_handle": repo_handle,
                    "repo_id": repo_id,
                    "requests_per_second": requests_per_second,
                    "run_id": run_id,
                    "runner_context": runner_context,
                    "tool_choice": tool_choice,
                    "tools": tools,
                    "use_or_fallback_to_workspace_secrets": use_or_fallback_to_workspace_secrets,
                },
                playground_experiment_stream_params.PlaygroundExperimentStreamParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class PlaygroundExperimentResourceWithRawResponse:
    def __init__(self, playground_experiment: PlaygroundExperimentResource) -> None:
        self._playground_experiment = playground_experiment

        self.batch = to_raw_response_wrapper(
            playground_experiment.batch,
        )
        self.stream = to_raw_response_wrapper(
            playground_experiment.stream,
        )


class AsyncPlaygroundExperimentResourceWithRawResponse:
    def __init__(self, playground_experiment: AsyncPlaygroundExperimentResource) -> None:
        self._playground_experiment = playground_experiment

        self.batch = async_to_raw_response_wrapper(
            playground_experiment.batch,
        )
        self.stream = async_to_raw_response_wrapper(
            playground_experiment.stream,
        )


class PlaygroundExperimentResourceWithStreamingResponse:
    def __init__(self, playground_experiment: PlaygroundExperimentResource) -> None:
        self._playground_experiment = playground_experiment

        self.batch = to_streamed_response_wrapper(
            playground_experiment.batch,
        )
        self.stream = to_streamed_response_wrapper(
            playground_experiment.stream,
        )


class AsyncPlaygroundExperimentResourceWithStreamingResponse:
    def __init__(self, playground_experiment: AsyncPlaygroundExperimentResource) -> None:
        self._playground_experiment = playground_experiment

        self.batch = async_to_streamed_response_wrapper(
            playground_experiment.batch,
        )
        self.stream = async_to_streamed_response_wrapper(
            playground_experiment.stream,
        )
