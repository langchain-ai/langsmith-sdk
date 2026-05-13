# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Union, Mapping, Iterable, Optional, cast
from datetime import datetime
from typing_extensions import Literal

import httpx

from .runs import (
    RunsResource,
    AsyncRunsResource,
    RunsResourceWithRawResponse,
    AsyncRunsResourceWithRawResponse,
    RunsResourceWithStreamingResponse,
    AsyncRunsResourceWithStreamingResponse,
)
from .group import (
    GroupResource,
    AsyncGroupResource,
    GroupResourceWithRawResponse,
    AsyncGroupResourceWithRawResponse,
    GroupResourceWithStreamingResponse,
    AsyncGroupResourceWithStreamingResponse,
)
from .share import (
    ShareResource,
    AsyncShareResource,
    ShareResourceWithRawResponse,
    AsyncShareResourceWithRawResponse,
    ShareResourceWithStreamingResponse,
    AsyncShareResourceWithStreamingResponse,
)
from .splits import (
    SplitsResource,
    AsyncSplitsResource,
    SplitsResourceWithRawResponse,
    AsyncSplitsResourceWithRawResponse,
    SplitsResourceWithStreamingResponse,
    AsyncSplitsResourceWithStreamingResponse,
)
from ...types import (
    DataType,
    SortByDatasetColumn,
    dataset_list_params,
    dataset_clone_params,
    dataset_create_params,
    dataset_update_params,
    dataset_upload_params,
    dataset_update_tags_params,
    dataset_retrieve_csv_params,
    dataset_retrieve_jsonl_params,
    dataset_retrieve_openai_params,
    dataset_retrieve_version_params,
    dataset_retrieve_openai_ft_params,
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
from .versions import (
    VersionsResource,
    AsyncVersionsResource,
    VersionsResourceWithRawResponse,
    AsyncVersionsResourceWithRawResponse,
    VersionsResourceWithStreamingResponse,
    AsyncVersionsResourceWithStreamingResponse,
)
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .comparative import (
    ComparativeResource,
    AsyncComparativeResource,
    ComparativeResourceWithRawResponse,
    AsyncComparativeResourceWithRawResponse,
    ComparativeResourceWithStreamingResponse,
    AsyncComparativeResourceWithStreamingResponse,
)
from .experiments import (
    ExperimentsResource,
    AsyncExperimentsResource,
    ExperimentsResourceWithRawResponse,
    AsyncExperimentsResourceWithRawResponse,
    ExperimentsResourceWithStreamingResponse,
    AsyncExperimentsResourceWithStreamingResponse,
)
from ...pagination import SyncOffsetPaginationTopLevelArray, AsyncOffsetPaginationTopLevelArray
from ..._base_client import AsyncPaginator, make_request_options
from ...types.dataset import Dataset
from ...types.data_type import DataType
from .playground_experiment import (
    PlaygroundExperimentResource,
    AsyncPlaygroundExperimentResource,
    PlaygroundExperimentResourceWithRawResponse,
    AsyncPlaygroundExperimentResourceWithRawResponse,
    PlaygroundExperimentResourceWithStreamingResponse,
    AsyncPlaygroundExperimentResourceWithStreamingResponse,
)
from ...types.dataset_version import DatasetVersion
from ...types.dataset_clone_response import DatasetCloneResponse
from ...types.sort_by_dataset_column import SortByDatasetColumn
from ...types.dataset_update_response import DatasetUpdateResponse
from ...types.dataset_transformation_param import DatasetTransformationParam

__all__ = ["DatasetsResource", "AsyncDatasetsResource"]


class DatasetsResource(SyncAPIResource):
    @cached_property
    def versions(self) -> VersionsResource:
        return VersionsResource(self._client)

    @cached_property
    def runs(self) -> RunsResource:
        return RunsResource(self._client)

    @cached_property
    def group(self) -> GroupResource:
        return GroupResource(self._client)

    @cached_property
    def experiments(self) -> ExperimentsResource:
        return ExperimentsResource(self._client)

    @cached_property
    def share(self) -> ShareResource:
        return ShareResource(self._client)

    @cached_property
    def comparative(self) -> ComparativeResource:
        return ComparativeResource(self._client)

    @cached_property
    def splits(self) -> SplitsResource:
        return SplitsResource(self._client)

    @cached_property
    def playground_experiment(self) -> PlaygroundExperimentResource:
        return PlaygroundExperimentResource(self._client)

    @cached_property
    def with_raw_response(self) -> DatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return DatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return DatasetsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        name: str,
        id: Optional[str] | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        data_type: DataType | Omit = omit,
        description: Optional[str] | Omit = omit,
        externally_managed: Optional[bool] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        inputs_schema_definition: Optional[Dict[str, object]] | Omit = omit,
        outputs_schema_definition: Optional[Dict[str, object]] | Omit = omit,
        transformations: Optional[Iterable[DatasetTransformationParam]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
          data_type: Enum for dataset data types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/datasets",
            body=maybe_transform(
                {
                    "name": name,
                    "id": id,
                    "created_at": created_at,
                    "data_type": data_type,
                    "description": description,
                    "externally_managed": externally_managed,
                    "extra": extra,
                    "inputs_schema_definition": inputs_schema_definition,
                    "outputs_schema_definition": outputs_schema_definition,
                    "transformations": transformations,
                },
                dataset_create_params.DatasetCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )

    def retrieve(
        self,
        dataset_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Get a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )

    def update(
        self,
        dataset_id: str,
        *,
        baseline_experiment_id: Optional[dataset_update_params.BaselineExperimentID] | Omit = omit,
        description: Optional[dataset_update_params.Description] | Omit = omit,
        inputs_schema_definition: Optional[dataset_update_params.InputsSchemaDefinition] | Omit = omit,
        metadata: Optional[dataset_update_params.Metadata] | Omit = omit,
        name: Optional[dataset_update_params.Name] | Omit = omit,
        outputs_schema_definition: Optional[dataset_update_params.OutputsSchemaDefinition] | Omit = omit,
        patch_examples: Optional[Dict[str, dataset_update_params.PatchExamples]] | Omit = omit,
        transformations: Optional[dataset_update_params.Transformations] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetUpdateResponse:
        """
        Update a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._patch(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "baseline_experiment_id": baseline_experiment_id,
                    "description": description,
                    "inputs_schema_definition": inputs_schema_definition,
                    "metadata": metadata,
                    "name": name,
                    "outputs_schema_definition": outputs_schema_definition,
                    "patch_examples": patch_examples,
                    "transformations": transformations,
                },
                dataset_update_params.DatasetUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetUpdateResponse,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        datatype: Union[List[DataType], DataType, None] | Omit = omit,
        exclude: Optional[List[Literal["example_count"]]] | Omit = omit,
        exclude_corrections_datasets: bool | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByDatasetColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncOffsetPaginationTopLevelArray[Dataset]:
        """
        Get all datasets by query params and owner.

        Args:
          datatype: Enum for dataset data types.

          sort_by: Enum for available dataset columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/datasets",
            page=SyncOffsetPaginationTopLevelArray[Dataset],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "datatype": datatype,
                        "exclude": exclude,
                        "exclude_corrections_datasets": exclude_corrections_datasets,
                        "limit": limit,
                        "metadata": metadata,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                    },
                    dataset_list_params.DatasetListParams,
                ),
            ),
            model=Dataset,
        )

    def delete(
        self,
        dataset_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._delete(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def clone(
        self,
        *,
        source_dataset_id: str,
        target_dataset_id: str,
        as_of: Union[Union[str, datetime], str, None] | Omit = omit,
        examples: SequenceNotStr[str] | Omit = omit,
        split: Union[str, SequenceNotStr[str], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetCloneResponse:
        """
        Clone a dataset.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/api/v1/datasets/clone",
            body=maybe_transform(
                {
                    "source_dataset_id": source_dataset_id,
                    "target_dataset_id": target_dataset_id,
                    "as_of": as_of,
                    "examples": examples,
                    "split": split,
                },
                dataset_clone_params.DatasetCloneParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetCloneResponse,
        )

    def retrieve_csv(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as CSV format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/csv", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"as_of": as_of}, dataset_retrieve_csv_params.DatasetRetrieveCsvParams),
            ),
            cast_to=object,
        )

    def retrieve_jsonl(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as CSV format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/jsonl", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"as_of": as_of}, dataset_retrieve_jsonl_params.DatasetRetrieveJSONLParams),
            ),
            cast_to=object,
        )

    def retrieve_openai(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as OpenAI Evals Jsonl format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/openai", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"as_of": as_of}, dataset_retrieve_openai_params.DatasetRetrieveOpenAIParams),
            ),
            cast_to=object,
        )

    def retrieve_openai_ft(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as OpenAI Jsonl format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/openai_ft", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"as_of": as_of}, dataset_retrieve_openai_ft_params.DatasetRetrieveOpenAIFtParams
                ),
            ),
            cast_to=object,
        )

    def retrieve_version(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        tag: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetVersion:
        """
        Get dataset version by as_of or exact tag.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._get(
            path_template("/api/v1/datasets/{dataset_id}/version", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "as_of": as_of,
                        "tag": tag,
                    },
                    dataset_retrieve_version_params.DatasetRetrieveVersionParams,
                ),
            ),
            cast_to=DatasetVersion,
        )

    def update_tags(
        self,
        dataset_id: str,
        *,
        as_of: Union[Union[str, datetime], str],
        tag: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetVersion:
        """
        Set a tag on a dataset version.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return self._put(
            path_template("/api/v1/datasets/{dataset_id}/tags", dataset_id=dataset_id),
            body=maybe_transform(
                {
                    "as_of": as_of,
                    "tag": tag,
                },
                dataset_update_tags_params.DatasetUpdateTagsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetVersion,
        )

    def upload(
        self,
        *,
        file: FileTypes,
        input_keys: SequenceNotStr[str],
        data_type: DataType | Omit = omit,
        description: Optional[str] | Omit = omit,
        input_key_mappings: Optional[str] | Omit = omit,
        inputs_schema_definition: Optional[str] | Omit = omit,
        metadata_key_mappings: Optional[str] | Omit = omit,
        metadata_keys: SequenceNotStr[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        output_key_mappings: Optional[str] | Omit = omit,
        output_keys: SequenceNotStr[str] | Omit = omit,
        outputs_schema_definition: Optional[str] | Omit = omit,
        transformations: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Create a new dataset from a CSV or JSONL file.

        Args:
          data_type: Enum for dataset data types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        body = deepcopy_minimal(
            {
                "file": file,
                "input_keys": input_keys,
                "data_type": data_type,
                "description": description,
                "input_key_mappings": input_key_mappings,
                "inputs_schema_definition": inputs_schema_definition,
                "metadata_key_mappings": metadata_key_mappings,
                "metadata_keys": metadata_keys,
                "name": name,
                "output_key_mappings": output_key_mappings,
                "output_keys": output_keys,
                "outputs_schema_definition": outputs_schema_definition,
                "transformations": transformations,
            }
        )
        files = extract_files(cast(Mapping[str, object], body), paths=[["file"]])
        # It should be noted that the actual Content-Type header that will be
        # sent to the server will contain a `boundary` parameter, e.g.
        # multipart/form-data; boundary=---abc--
        extra_headers = {"Content-Type": "multipart/form-data", **(extra_headers or {})}
        return self._post(
            "/api/v1/datasets/upload",
            body=maybe_transform(body, dataset_upload_params.DatasetUploadParams),
            files=files,
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )


class AsyncDatasetsResource(AsyncAPIResource):
    @cached_property
    def versions(self) -> AsyncVersionsResource:
        return AsyncVersionsResource(self._client)

    @cached_property
    def runs(self) -> AsyncRunsResource:
        return AsyncRunsResource(self._client)

    @cached_property
    def group(self) -> AsyncGroupResource:
        return AsyncGroupResource(self._client)

    @cached_property
    def experiments(self) -> AsyncExperimentsResource:
        return AsyncExperimentsResource(self._client)

    @cached_property
    def share(self) -> AsyncShareResource:
        return AsyncShareResource(self._client)

    @cached_property
    def comparative(self) -> AsyncComparativeResource:
        return AsyncComparativeResource(self._client)

    @cached_property
    def splits(self) -> AsyncSplitsResource:
        return AsyncSplitsResource(self._client)

    @cached_property
    def playground_experiment(self) -> AsyncPlaygroundExperimentResource:
        return AsyncPlaygroundExperimentResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncDatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/langsmith-api-python#with_streaming_response
        """
        return AsyncDatasetsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        name: str,
        id: Optional[str] | Omit = omit,
        created_at: Union[str, datetime] | Omit = omit,
        data_type: DataType | Omit = omit,
        description: Optional[str] | Omit = omit,
        externally_managed: Optional[bool] | Omit = omit,
        extra: Optional[Dict[str, object]] | Omit = omit,
        inputs_schema_definition: Optional[Dict[str, object]] | Omit = omit,
        outputs_schema_definition: Optional[Dict[str, object]] | Omit = omit,
        transformations: Optional[Iterable[DatasetTransformationParam]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
          data_type: Enum for dataset data types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/datasets",
            body=await async_maybe_transform(
                {
                    "name": name,
                    "id": id,
                    "created_at": created_at,
                    "data_type": data_type,
                    "description": description,
                    "externally_managed": externally_managed,
                    "extra": extra,
                    "inputs_schema_definition": inputs_schema_definition,
                    "outputs_schema_definition": outputs_schema_definition,
                    "transformations": transformations,
                },
                dataset_create_params.DatasetCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )

    async def retrieve(
        self,
        dataset_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Get a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )

    async def update(
        self,
        dataset_id: str,
        *,
        baseline_experiment_id: Optional[dataset_update_params.BaselineExperimentID] | Omit = omit,
        description: Optional[dataset_update_params.Description] | Omit = omit,
        inputs_schema_definition: Optional[dataset_update_params.InputsSchemaDefinition] | Omit = omit,
        metadata: Optional[dataset_update_params.Metadata] | Omit = omit,
        name: Optional[dataset_update_params.Name] | Omit = omit,
        outputs_schema_definition: Optional[dataset_update_params.OutputsSchemaDefinition] | Omit = omit,
        patch_examples: Optional[Dict[str, dataset_update_params.PatchExamples]] | Omit = omit,
        transformations: Optional[dataset_update_params.Transformations] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetUpdateResponse:
        """
        Update a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._patch(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "baseline_experiment_id": baseline_experiment_id,
                    "description": description,
                    "inputs_schema_definition": inputs_schema_definition,
                    "metadata": metadata,
                    "name": name,
                    "outputs_schema_definition": outputs_schema_definition,
                    "patch_examples": patch_examples,
                    "transformations": transformations,
                },
                dataset_update_params.DatasetUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetUpdateResponse,
        )

    def list(
        self,
        *,
        id: Optional[SequenceNotStr[str]] | Omit = omit,
        datatype: Union[List[DataType], DataType, None] | Omit = omit,
        exclude: Optional[List[Literal["example_count"]]] | Omit = omit,
        exclude_corrections_datasets: bool | Omit = omit,
        limit: int | Omit = omit,
        metadata: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        name_contains: Optional[str] | Omit = omit,
        offset: int | Omit = omit,
        sort_by: SortByDatasetColumn | Omit = omit,
        sort_by_desc: bool | Omit = omit,
        tag_value_id: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncPaginator[Dataset, AsyncOffsetPaginationTopLevelArray[Dataset]]:
        """
        Get all datasets by query params and owner.

        Args:
          datatype: Enum for dataset data types.

          sort_by: Enum for available dataset columns to sort by.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get_api_list(
            "/api/v1/datasets",
            page=AsyncOffsetPaginationTopLevelArray[Dataset],
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "id": id,
                        "datatype": datatype,
                        "exclude": exclude,
                        "exclude_corrections_datasets": exclude_corrections_datasets,
                        "limit": limit,
                        "metadata": metadata,
                        "name": name,
                        "name_contains": name_contains,
                        "offset": offset,
                        "sort_by": sort_by,
                        "sort_by_desc": sort_by_desc,
                        "tag_value_id": tag_value_id,
                    },
                    dataset_list_params.DatasetListParams,
                ),
            ),
            model=Dataset,
        )

    async def delete(
        self,
        dataset_id: str,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Delete a specific dataset.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._delete(
            path_template("/api/v1/datasets/{dataset_id}", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def clone(
        self,
        *,
        source_dataset_id: str,
        target_dataset_id: str,
        as_of: Union[Union[str, datetime], str, None] | Omit = omit,
        examples: SequenceNotStr[str] | Omit = omit,
        split: Union[str, SequenceNotStr[str], None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetCloneResponse:
        """
        Clone a dataset.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/api/v1/datasets/clone",
            body=await async_maybe_transform(
                {
                    "source_dataset_id": source_dataset_id,
                    "target_dataset_id": target_dataset_id,
                    "as_of": as_of,
                    "examples": examples,
                    "split": split,
                },
                dataset_clone_params.DatasetCloneParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetCloneResponse,
        )

    async def retrieve_csv(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as CSV format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/csv", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"as_of": as_of}, dataset_retrieve_csv_params.DatasetRetrieveCsvParams
                ),
            ),
            cast_to=object,
        )

    async def retrieve_jsonl(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as CSV format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/jsonl", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"as_of": as_of}, dataset_retrieve_jsonl_params.DatasetRetrieveJSONLParams
                ),
            ),
            cast_to=object,
        )

    async def retrieve_openai(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as OpenAI Evals Jsonl format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/openai", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"as_of": as_of}, dataset_retrieve_openai_params.DatasetRetrieveOpenAIParams
                ),
            ),
            cast_to=object,
        )

    async def retrieve_openai_ft(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Download a dataset as OpenAI Jsonl format.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/openai_ft", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"as_of": as_of}, dataset_retrieve_openai_ft_params.DatasetRetrieveOpenAIFtParams
                ),
            ),
            cast_to=object,
        )

    async def retrieve_version(
        self,
        dataset_id: str,
        *,
        as_of: Union[str, datetime, None] | Omit = omit,
        tag: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetVersion:
        """
        Get dataset version by as_of or exact tag.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._get(
            path_template("/api/v1/datasets/{dataset_id}/version", dataset_id=dataset_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "as_of": as_of,
                        "tag": tag,
                    },
                    dataset_retrieve_version_params.DatasetRetrieveVersionParams,
                ),
            ),
            cast_to=DatasetVersion,
        )

    async def update_tags(
        self,
        dataset_id: str,
        *,
        as_of: Union[Union[str, datetime], str],
        tag: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetVersion:
        """
        Set a tag on a dataset version.

        Args:
          as_of: Only modifications made on or before this time are included. If None, the latest
              version of the dataset is used.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not dataset_id:
            raise ValueError(f"Expected a non-empty value for `dataset_id` but received {dataset_id!r}")
        return await self._put(
            path_template("/api/v1/datasets/{dataset_id}/tags", dataset_id=dataset_id),
            body=await async_maybe_transform(
                {
                    "as_of": as_of,
                    "tag": tag,
                },
                dataset_update_tags_params.DatasetUpdateTagsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetVersion,
        )

    async def upload(
        self,
        *,
        file: FileTypes,
        input_keys: SequenceNotStr[str],
        data_type: DataType | Omit = omit,
        description: Optional[str] | Omit = omit,
        input_key_mappings: Optional[str] | Omit = omit,
        inputs_schema_definition: Optional[str] | Omit = omit,
        metadata_key_mappings: Optional[str] | Omit = omit,
        metadata_keys: SequenceNotStr[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        output_key_mappings: Optional[str] | Omit = omit,
        output_keys: SequenceNotStr[str] | Omit = omit,
        outputs_schema_definition: Optional[str] | Omit = omit,
        transformations: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> Dataset:
        """
        Create a new dataset from a CSV or JSONL file.

        Args:
          data_type: Enum for dataset data types.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        body = deepcopy_minimal(
            {
                "file": file,
                "input_keys": input_keys,
                "data_type": data_type,
                "description": description,
                "input_key_mappings": input_key_mappings,
                "inputs_schema_definition": inputs_schema_definition,
                "metadata_key_mappings": metadata_key_mappings,
                "metadata_keys": metadata_keys,
                "name": name,
                "output_key_mappings": output_key_mappings,
                "output_keys": output_keys,
                "outputs_schema_definition": outputs_schema_definition,
                "transformations": transformations,
            }
        )
        files = extract_files(cast(Mapping[str, object], body), paths=[["file"]])
        # It should be noted that the actual Content-Type header that will be
        # sent to the server will contain a `boundary` parameter, e.g.
        # multipart/form-data; boundary=---abc--
        extra_headers = {"Content-Type": "multipart/form-data", **(extra_headers or {})}
        return await self._post(
            "/api/v1/datasets/upload",
            body=await async_maybe_transform(body, dataset_upload_params.DatasetUploadParams),
            files=files,
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=Dataset,
        )


class DatasetsResourceWithRawResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

        self.create = to_raw_response_wrapper(
            datasets.create,
        )
        self.retrieve = to_raw_response_wrapper(
            datasets.retrieve,
        )
        self.update = to_raw_response_wrapper(
            datasets.update,
        )
        self.list = to_raw_response_wrapper(
            datasets.list,
        )
        self.delete = to_raw_response_wrapper(
            datasets.delete,
        )
        self.clone = to_raw_response_wrapper(
            datasets.clone,
        )
        self.retrieve_csv = to_raw_response_wrapper(
            datasets.retrieve_csv,
        )
        self.retrieve_jsonl = to_raw_response_wrapper(
            datasets.retrieve_jsonl,
        )
        self.retrieve_openai = to_raw_response_wrapper(
            datasets.retrieve_openai,
        )
        self.retrieve_openai_ft = to_raw_response_wrapper(
            datasets.retrieve_openai_ft,
        )
        self.retrieve_version = to_raw_response_wrapper(
            datasets.retrieve_version,
        )
        self.update_tags = to_raw_response_wrapper(
            datasets.update_tags,
        )
        self.upload = to_raw_response_wrapper(
            datasets.upload,
        )

    @cached_property
    def versions(self) -> VersionsResourceWithRawResponse:
        return VersionsResourceWithRawResponse(self._datasets.versions)

    @cached_property
    def runs(self) -> RunsResourceWithRawResponse:
        return RunsResourceWithRawResponse(self._datasets.runs)

    @cached_property
    def group(self) -> GroupResourceWithRawResponse:
        return GroupResourceWithRawResponse(self._datasets.group)

    @cached_property
    def experiments(self) -> ExperimentsResourceWithRawResponse:
        return ExperimentsResourceWithRawResponse(self._datasets.experiments)

    @cached_property
    def share(self) -> ShareResourceWithRawResponse:
        return ShareResourceWithRawResponse(self._datasets.share)

    @cached_property
    def comparative(self) -> ComparativeResourceWithRawResponse:
        return ComparativeResourceWithRawResponse(self._datasets.comparative)

    @cached_property
    def splits(self) -> SplitsResourceWithRawResponse:
        return SplitsResourceWithRawResponse(self._datasets.splits)

    @cached_property
    def playground_experiment(self) -> PlaygroundExperimentResourceWithRawResponse:
        return PlaygroundExperimentResourceWithRawResponse(self._datasets.playground_experiment)


class AsyncDatasetsResourceWithRawResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

        self.create = async_to_raw_response_wrapper(
            datasets.create,
        )
        self.retrieve = async_to_raw_response_wrapper(
            datasets.retrieve,
        )
        self.update = async_to_raw_response_wrapper(
            datasets.update,
        )
        self.list = async_to_raw_response_wrapper(
            datasets.list,
        )
        self.delete = async_to_raw_response_wrapper(
            datasets.delete,
        )
        self.clone = async_to_raw_response_wrapper(
            datasets.clone,
        )
        self.retrieve_csv = async_to_raw_response_wrapper(
            datasets.retrieve_csv,
        )
        self.retrieve_jsonl = async_to_raw_response_wrapper(
            datasets.retrieve_jsonl,
        )
        self.retrieve_openai = async_to_raw_response_wrapper(
            datasets.retrieve_openai,
        )
        self.retrieve_openai_ft = async_to_raw_response_wrapper(
            datasets.retrieve_openai_ft,
        )
        self.retrieve_version = async_to_raw_response_wrapper(
            datasets.retrieve_version,
        )
        self.update_tags = async_to_raw_response_wrapper(
            datasets.update_tags,
        )
        self.upload = async_to_raw_response_wrapper(
            datasets.upload,
        )

    @cached_property
    def versions(self) -> AsyncVersionsResourceWithRawResponse:
        return AsyncVersionsResourceWithRawResponse(self._datasets.versions)

    @cached_property
    def runs(self) -> AsyncRunsResourceWithRawResponse:
        return AsyncRunsResourceWithRawResponse(self._datasets.runs)

    @cached_property
    def group(self) -> AsyncGroupResourceWithRawResponse:
        return AsyncGroupResourceWithRawResponse(self._datasets.group)

    @cached_property
    def experiments(self) -> AsyncExperimentsResourceWithRawResponse:
        return AsyncExperimentsResourceWithRawResponse(self._datasets.experiments)

    @cached_property
    def share(self) -> AsyncShareResourceWithRawResponse:
        return AsyncShareResourceWithRawResponse(self._datasets.share)

    @cached_property
    def comparative(self) -> AsyncComparativeResourceWithRawResponse:
        return AsyncComparativeResourceWithRawResponse(self._datasets.comparative)

    @cached_property
    def splits(self) -> AsyncSplitsResourceWithRawResponse:
        return AsyncSplitsResourceWithRawResponse(self._datasets.splits)

    @cached_property
    def playground_experiment(self) -> AsyncPlaygroundExperimentResourceWithRawResponse:
        return AsyncPlaygroundExperimentResourceWithRawResponse(self._datasets.playground_experiment)


class DatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: DatasetsResource) -> None:
        self._datasets = datasets

        self.create = to_streamed_response_wrapper(
            datasets.create,
        )
        self.retrieve = to_streamed_response_wrapper(
            datasets.retrieve,
        )
        self.update = to_streamed_response_wrapper(
            datasets.update,
        )
        self.list = to_streamed_response_wrapper(
            datasets.list,
        )
        self.delete = to_streamed_response_wrapper(
            datasets.delete,
        )
        self.clone = to_streamed_response_wrapper(
            datasets.clone,
        )
        self.retrieve_csv = to_streamed_response_wrapper(
            datasets.retrieve_csv,
        )
        self.retrieve_jsonl = to_streamed_response_wrapper(
            datasets.retrieve_jsonl,
        )
        self.retrieve_openai = to_streamed_response_wrapper(
            datasets.retrieve_openai,
        )
        self.retrieve_openai_ft = to_streamed_response_wrapper(
            datasets.retrieve_openai_ft,
        )
        self.retrieve_version = to_streamed_response_wrapper(
            datasets.retrieve_version,
        )
        self.update_tags = to_streamed_response_wrapper(
            datasets.update_tags,
        )
        self.upload = to_streamed_response_wrapper(
            datasets.upload,
        )

    @cached_property
    def versions(self) -> VersionsResourceWithStreamingResponse:
        return VersionsResourceWithStreamingResponse(self._datasets.versions)

    @cached_property
    def runs(self) -> RunsResourceWithStreamingResponse:
        return RunsResourceWithStreamingResponse(self._datasets.runs)

    @cached_property
    def group(self) -> GroupResourceWithStreamingResponse:
        return GroupResourceWithStreamingResponse(self._datasets.group)

    @cached_property
    def experiments(self) -> ExperimentsResourceWithStreamingResponse:
        return ExperimentsResourceWithStreamingResponse(self._datasets.experiments)

    @cached_property
    def share(self) -> ShareResourceWithStreamingResponse:
        return ShareResourceWithStreamingResponse(self._datasets.share)

    @cached_property
    def comparative(self) -> ComparativeResourceWithStreamingResponse:
        return ComparativeResourceWithStreamingResponse(self._datasets.comparative)

    @cached_property
    def splits(self) -> SplitsResourceWithStreamingResponse:
        return SplitsResourceWithStreamingResponse(self._datasets.splits)

    @cached_property
    def playground_experiment(self) -> PlaygroundExperimentResourceWithStreamingResponse:
        return PlaygroundExperimentResourceWithStreamingResponse(self._datasets.playground_experiment)


class AsyncDatasetsResourceWithStreamingResponse:
    def __init__(self, datasets: AsyncDatasetsResource) -> None:
        self._datasets = datasets

        self.create = async_to_streamed_response_wrapper(
            datasets.create,
        )
        self.retrieve = async_to_streamed_response_wrapper(
            datasets.retrieve,
        )
        self.update = async_to_streamed_response_wrapper(
            datasets.update,
        )
        self.list = async_to_streamed_response_wrapper(
            datasets.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            datasets.delete,
        )
        self.clone = async_to_streamed_response_wrapper(
            datasets.clone,
        )
        self.retrieve_csv = async_to_streamed_response_wrapper(
            datasets.retrieve_csv,
        )
        self.retrieve_jsonl = async_to_streamed_response_wrapper(
            datasets.retrieve_jsonl,
        )
        self.retrieve_openai = async_to_streamed_response_wrapper(
            datasets.retrieve_openai,
        )
        self.retrieve_openai_ft = async_to_streamed_response_wrapper(
            datasets.retrieve_openai_ft,
        )
        self.retrieve_version = async_to_streamed_response_wrapper(
            datasets.retrieve_version,
        )
        self.update_tags = async_to_streamed_response_wrapper(
            datasets.update_tags,
        )
        self.upload = async_to_streamed_response_wrapper(
            datasets.upload,
        )

    @cached_property
    def versions(self) -> AsyncVersionsResourceWithStreamingResponse:
        return AsyncVersionsResourceWithStreamingResponse(self._datasets.versions)

    @cached_property
    def runs(self) -> AsyncRunsResourceWithStreamingResponse:
        return AsyncRunsResourceWithStreamingResponse(self._datasets.runs)

    @cached_property
    def group(self) -> AsyncGroupResourceWithStreamingResponse:
        return AsyncGroupResourceWithStreamingResponse(self._datasets.group)

    @cached_property
    def experiments(self) -> AsyncExperimentsResourceWithStreamingResponse:
        return AsyncExperimentsResourceWithStreamingResponse(self._datasets.experiments)

    @cached_property
    def share(self) -> AsyncShareResourceWithStreamingResponse:
        return AsyncShareResourceWithStreamingResponse(self._datasets.share)

    @cached_property
    def comparative(self) -> AsyncComparativeResourceWithStreamingResponse:
        return AsyncComparativeResourceWithStreamingResponse(self._datasets.comparative)

    @cached_property
    def splits(self) -> AsyncSplitsResourceWithStreamingResponse:
        return AsyncSplitsResourceWithStreamingResponse(self._datasets.splits)

    @cached_property
    def playground_experiment(self) -> AsyncPlaygroundExperimentResourceWithStreamingResponse:
        return AsyncPlaygroundExperimentResourceWithStreamingResponse(self._datasets.playground_experiment)
