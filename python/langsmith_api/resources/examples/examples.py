# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Union, Mapping, Optional, cast
from datetime import datetime
from typing_extensions import Literal

import httpx

from .bulk import (
    BulkResource,
    AsyncBulkResource,
    BulkResourceWithRawResponse,
    AsyncBulkResourceWithRawResponse,
    BulkResourceWithStreamingResponse,
    AsyncBulkResourceWithStreamingResponse,
)
from ...types import (
    example_list_params,
    example_create_params,
    example_update_params,
    example_retrieve_params,
    example_delete_all_params,
    example_retrieve_count_params,
    example_upload_from_csv_params,
)
from ..._types import (
    Body,
    Omit,
    Query,
    Headers,
    NotGiven,
    FileTypes,
    SequenceNotStr,
    omit,
    not_given,
)
from ..._utils import extract_files, path_template, maybe_transform, deepcopy_minimal, async_maybe_transform
from .validate import (
    ValidateResource,
    AsyncValidateResource,
    ValidateResourceWithRawResponse,
    AsyncValidateResourceWithRawResponse,
    ValidateResourceWithStreamingResponse,
    AsyncValidateResourceWithStreamingResponse,
)
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
from ...types.example import Example
from ...types.example_select import ExampleSelect
from ...types.attachments_operations_param import AttachmentsOperationsParam
from ...types.example_retrieve_count_response import ExampleRetrieveCountResponse
from ...types.example_upload_from_csv_response import ExampleUploadFromCsvResponse

__all__ = ["ExamplesResource", "AsyncExamplesResource"]


class ExamplesResource(SyncAPIResource):
    @cached_property
    def bulk(self) -> BulkResource:
        return BulkResource(self._client)

    @cached_property
    def validate(self) -> ValidateResource:
        return ValidateResource(self._client)

    @cached_property
    def with_raw_response(self) -> ExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return ExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return ExamplesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        dataset_id: str,
        id: Optional[str] | Omit = omit,
        created_at: str | Omit = omit,
        inputs: Optional[Dict[str, object]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        outputs: Optional[Dict[str, object]] | Omit = omit,
        source_run_id: Optional[str] | Omit = omit,
        split: Union[SequenceNotStr[str], str, None] | Omit = omit,
        use_legacy_message_format: bool | Omit = omit,
        use_source_run_attachments: SequenceNotStr[str] | Omit = omit,
        use_source_run_io: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Example:
        """
        Create a new example.

        Args:
          use_legacy_message_format: Use Legacy Message Format for LLM runs

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/examples",
            body=maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "id": id,
                    "created_at": created_at,
                    "inputs": inputs,
                    "metadata": metadata,
                    "outputs": outputs,
                    "source_run_id": source_run_id,
                    "split": split,
                    "use_legacy_message_format": use_legacy_message_format,
                    "use_source_run_attachments": use_source_run_attachments,
                    "use_source_run_io": use_source_run_io,
                },
                example_create_params.ExampleCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Example,
        )

    def retrieve(
        self,
        example_id: str,
        *,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Example:
        """
        Get a specific example.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return self._get(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "as_of": as_of,
                        "dataset": dataset,
                    },
                    example_retrieve_params.ExampleRetrieveParams,
                ),
            ),
            cast_to=Example,
        )

    def update(
        self,
        example_id: str,
        *,
        attachments_operations: Optional[AttachmentsOperationsParam] | Omit = omit,
        dataset_id: Optional[str] | Omit = omit,
        inputs: Optional[Dict[str, object]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        outputs: Optional[Dict[str, object]] | Omit = omit,
        overwrite: bool | Omit = omit,
        split: Union[SequenceNotStr[str], str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update a specific example.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return self._patch(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            body=maybe_transform(
                {
                    "attachments_operations": attachments_operations,
                    "dataset_id": dataset_id,
                    "inputs": inputs,
                    "metadata": metadata,
                    "outputs": outputs,
                    "overwrite": overwrite,
                    "split": split,
                },
                example_update_params.ExampleUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        descending: Optional[bool] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        full_text_contains: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        order: Literal["recent", "random", "recently_created", "id"] | Omit = omit,
        random_seed: Optional[float] | Omit = omit,
        select: List[ExampleSelect] | Omit = omit,
        splits: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[Example]:
        """
        Get all examples by query params

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/examples",
            page=SyncOffsetPaginationTopLevelArray[Example],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "dataset": dataset,
                        "descending": descending,
                        "filter": filter,
                        "full_text_contains": full_text_contains,
                        "limit": limit,
                        "metadata": metadata,
                        "offset": offset,
                        "order": order,
                        "random_seed": random_seed,
                        "select": select,
                        "splits": splits,
                    },
                    example_list_params.ExampleListParams,
                ),
            ),
            model=Example,
        )

    def delete(
        self,
        example_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Soft delete an example.

        Only deletes the example in the 'latest' version of the
        dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return self._delete(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def delete_all(
        self,
        *,
        example_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Soft delete examples.

        Only deletes the examples in the 'latest' version of the
        dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._delete(
            "/api/v1/examples",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"example_ids": example_ids}, example_delete_all_params.ExampleDeleteAllParams),
            ),
            cast_to=object,
        )

    def retrieve_count(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        full_text_contains: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        splits: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleRetrieveCountResponse:
        """
        Count all examples by query params

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/api/v1/examples/count",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "dataset": dataset,
                        "filter": filter,
                        "full_text_contains": full_text_contains,
                        "metadata": metadata,
                        "splits": splits,
                    },
                    example_retrieve_count_params.ExampleRetrieveCountParams,
                ),
            ),
            cast_to=int,
        )

    def upload_from_csv(
        self,
        dataset_id: str,
        *,
        file: FileTypes,
        input_keys: SequenceNotStr[str],
        metadata_keys: SequenceNotStr[str] | Omit = omit,
        output_keys: SequenceNotStr[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleUploadFromCsvResponse:
        """
        Upload examples from a CSV file.

        Note: For non-csv upload, please use the POST
        /v1/platform/datasets/{dataset_id}/examples endpoint which provides more
        efficient upload.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        body = deepcopy_minimal(
            {
                "file": file,
                "input_keys": input_keys,
                "metadata_keys": metadata_keys,
                "output_keys": output_keys,
            }
        )
        files = extract_files(cast(Mapping[str, object], body), paths=[["file"]])
        # It should be noted that the actual Content-Type header that will be
        # sent to the server will contain a `boundary` parameter, e.g.
        # multipart/form-data; boundary=---abc--
        extra_headers = {"Content-Type": "multipart/form-data", **(extra_headers or {})}
        return self._post(
            path_template("/api/v1/examples/upload/{dataset_id}", dataset_id=dataset_id),
            body=maybe_transform(body, example_upload_from_csv_params.ExampleUploadFromCsvParams),
            files=files,
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ExampleUploadFromCsvResponse,
        )


class AsyncExamplesResource(AsyncAPIResource):
    @cached_property
    def bulk(self) -> AsyncBulkResource:
        return AsyncBulkResource(self._client)

    @cached_property
    def validate(self) -> AsyncValidateResource:
        return AsyncValidateResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncExamplesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncExamplesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncExamplesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncExamplesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        dataset_id: str,
        id: Optional[str] | Omit = omit,
        created_at: str | Omit = omit,
        inputs: Optional[Dict[str, object]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        outputs: Optional[Dict[str, object]] | Omit = omit,
        source_run_id: Optional[str] | Omit = omit,
        split: Union[SequenceNotStr[str], str, None] | Omit = omit,
        use_legacy_message_format: bool | Omit = omit,
        use_source_run_attachments: SequenceNotStr[str] | Omit = omit,
        use_source_run_io: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Example:
        """
        Create a new example.

        Args:
          use_legacy_message_format: Use Legacy Message Format for LLM runs

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/examples",
            body=await async_maybe_transform(
                {
                    "dataset_id": dataset_id,
                    "id": id,
                    "created_at": created_at,
                    "inputs": inputs,
                    "metadata": metadata,
                    "outputs": outputs,
                    "source_run_id": source_run_id,
                    "split": split,
                    "use_legacy_message_format": use_legacy_message_format,
                    "use_source_run_attachments": use_source_run_attachments,
                    "use_source_run_io": use_source_run_io,
                },
                example_create_params.ExampleCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Example,
        )

    async def retrieve(
        self,
        example_id: str,
        *,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Example:
        """
        Get a specific example.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return await self._get(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "as_of": as_of,
                        "dataset": dataset,
                    },
                    example_retrieve_params.ExampleRetrieveParams,
                ),
            ),
            cast_to=Example,
        )

    async def update(
        self,
        example_id: str,
        *,
        attachments_operations: Optional[AttachmentsOperationsParam] | Omit = omit,
        dataset_id: Optional[str] | Omit = omit,
        inputs: Optional[Dict[str, object]] | Omit = omit,
        metadata: Optional[Dict[str, object]] | Omit = omit,
        outputs: Optional[Dict[str, object]] | Omit = omit,
        overwrite: bool | Omit = omit,
        split: Union[SequenceNotStr[str], str, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Update a specific example.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return await self._patch(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            body=await async_maybe_transform(
                {
                    "attachments_operations": attachments_operations,
                    "dataset_id": dataset_id,
                    "inputs": inputs,
                    "metadata": metadata,
                    "outputs": outputs,
                    "overwrite": overwrite,
                    "split": split,
                },
                example_update_params.ExampleUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        descending: Optional[bool] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        full_text_contains: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        order: Literal["recent", "random", "recently_created", "id"] | Omit = omit,
        random_seed: Optional[float] | Omit = omit,
        select: List[ExampleSelect] | Omit = omit,
        splits: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[Example, AsyncOffsetPaginationTopLevelArray[Example]]:
        """
        Get all examples by query params

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/examples",
            page=AsyncOffsetPaginationTopLevelArray[Example],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "dataset": dataset,
                        "descending": descending,
                        "filter": filter,
                        "full_text_contains": full_text_contains,
                        "limit": limit,
                        "metadata": metadata,
                        "offset": offset,
                        "order": order,
                        "random_seed": random_seed,
                        "select": select,
                        "splits": splits,
                    },
                    example_list_params.ExampleListParams,
                ),
            ),
            model=Example,
        )

    async def delete(
        self,
        example_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Soft delete an example.

        Only deletes the example in the 'latest' version of the
        dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not example_id:
            raise ValueError(f"Expected a non-empty value for `example_id` but received {example_id!r}")
        return await self._delete(
            path_template("/api/v1/examples/{example_id}", example_id=example_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def delete_all(
        self,
        *,
        example_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Soft delete examples.

        Only deletes the examples in the 'latest' version of the
        dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._delete(
            "/api/v1/examples",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"example_ids": example_ids}, example_delete_all_params.ExampleDeleteAllParams
                ),
            ),
            cast_to=object,
        )

    async def retrieve_count(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        as_of: Union[Union[str, datetime], str] | Omit = omit,
        dataset: Optional[str] | Omit = omit,
        filter: Optional[str] | Omit = omit,
        full_text_contains: Optional[SequenceNotStr[str]] | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        splits: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleRetrieveCountResponse:
        """
        Count all examples by query params

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/api/v1/examples/count",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "id": id,
                        "as_of": as_of,
                        "dataset": dataset,
                        "filter": filter,
                        "full_text_contains": full_text_contains,
                        "metadata": metadata,
                        "splits": splits,
                    },
                    example_retrieve_count_params.ExampleRetrieveCountParams,
                ),
            ),
            cast_to=int,
        )

    async def upload_from_csv(
        self,
        dataset_id: str,
        *,
        file: FileTypes,
        input_keys: SequenceNotStr[str],
        metadata_keys: SequenceNotStr[str] | Omit = omit,
        output_keys: SequenceNotStr[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ExampleUploadFromCsvResponse:
        """
        Upload examples from a CSV file.

        Note: For non-csv upload, please use the POST
        /v1/platform/datasets/{dataset_id}/examples endpoint which provides more
        efficient upload.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        body = deepcopy_minimal(
            {
                "file": file,
                "input_keys": input_keys,
                "metadata_keys": metadata_keys,
                "output_keys": output_keys,
            }
        )
        files = extract_files(cast(Mapping[str, object], body), paths=[["file"]])
        # It should be noted that the actual Content-Type header that will be
        # sent to the server will contain a `boundary` parameter, e.g.
        # multipart/form-data; boundary=---abc--
        extra_headers = {"Content-Type": "multipart/form-data", **(extra_headers or {})}
        return await self._post(
            path_template("/api/v1/examples/upload/{dataset_id}", dataset_id=dataset_id),
            body=await async_maybe_transform(body, example_upload_from_csv_params.ExampleUploadFromCsvParams),
            files=files,
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ExampleUploadFromCsvResponse,
        )


class ExamplesResourceWithRawResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.create = to_raw_response_wrapper(
            examples.create,
        )
        self.retrieve = to_raw_response_wrapper(
            examples.retrieve,
        )
        self.update = to_raw_response_wrapper(
            examples.update,
        )
        self.list = to_raw_response_wrapper(
            examples.list,
        )
        self.delete = to_raw_response_wrapper(
            examples.delete,
        )
        self.delete_all = to_raw_response_wrapper(
            examples.delete_all,
        )
        self.retrieve_count = to_raw_response_wrapper(
            examples.retrieve_count,
        )
        self.upload_from_csv = to_raw_response_wrapper(
            examples.upload_from_csv,
        )

    @cached_property
    def bulk(self) -> BulkResourceWithRawResponse:
        return BulkResourceWithRawResponse(self._examples.bulk)

    @cached_property
    def validate(self) -> ValidateResourceWithRawResponse:
        return ValidateResourceWithRawResponse(self._examples.validate)


class AsyncExamplesResourceWithRawResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.create = async_to_raw_response_wrapper(
            examples.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            examples.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            examples.update,
        )
        self.list = async_to_raw_response_wrapper(
            examples.list,
        )
        self.delete = async_to_raw_response_wrapper(
            examples.delete,
        )
        self.delete_all = async_to_raw_response_wrapper(
            examples.delete_all,
        )
        self.retrieve_count = async_to_raw_response_wrapper(
            examples.retrieve_count,
        )
        self.upload_from_csv = async_to_raw_response_wrapper(
            examples.upload_from_csv,
        )

    @cached_property
    def bulk(self) -> AsyncBulkResourceWithRawResponse:
        return AsyncBulkResourceWithRawResponse(self._examples.bulk)

    @cached_property
    def validate(self) -> AsyncValidateResourceWithRawResponse:
        return AsyncValidateResourceWithRawResponse(self._examples.validate)


class ExamplesResourceWithStreamingResponse:
    def __init__(self, examples: ExamplesResource) -> None:
        self._examples = examples

        self.create = to_streamed_response_wrapper(
            examples.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            examples.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            examples.update,
        )
        self.list = to_streamed_response_wrapper(
            examples.list,
        )
        self.delete = to_streamed_response_wrapper(
            examples.delete,
        )
        self.delete_all = to_streamed_response_wrapper(
            examples.delete_all,
        )
        self.retrieve_count = to_streamed_response_wrapper(
            examples.retrieve_count,
        )
        self.upload_from_csv = to_streamed_response_wrapper(
            examples.upload_from_csv,
        )

    @cached_property
    def bulk(self) -> BulkResourceWithStreamingResponse:
        return BulkResourceWithStreamingResponse(self._examples.bulk)

    @cached_property
    def validate(self) -> ValidateResourceWithStreamingResponse:
        return ValidateResourceWithStreamingResponse(self._examples.validate)


class AsyncExamplesResourceWithStreamingResponse:
    def __init__(self, examples: AsyncExamplesResource) -> None:
        self._examples = examples

        self.create = async_to_streamed_response_wrapper(
            examples.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            examples.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            examples.update,
        )
        self.list = async_to_streamed_response_wrapper(
            examples.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            examples.delete,
        )
        self.delete_all = async_to_streamed_response_wrapper(
            examples.delete_all,
        )
        self.retrieve_count = async_to_streamed_response_wrapper(
            examples.retrieve_count,
        )
        self.upload_from_csv = async_to_streamed_response_wrapper(
            examples.upload_from_csv,
        )

    @cached_property
    def bulk(self) -> AsyncBulkResourceWithStreamingResponse:
        return AsyncBulkResourceWithStreamingResponse(self._examples.bulk)

    @cached_property
    def validate(self) -> AsyncValidateResourceWithStreamingResponse:
        return AsyncValidateResourceWithStreamingResponse(self._examples.validate)
