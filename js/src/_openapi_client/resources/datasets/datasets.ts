// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ComparativeAPI from './comparative.js';
import {
  Comparative,
  ComparativeCreateParams,
  ComparativeCreateResponse,
  ComparativeDeleteResponse,
  SimpleExperimentInfo,
  SortByComparativeExperimentColumn,
} from './comparative.js';
import * as ExperimentRunsAPI from './experiment-runs.js';
import {
  ExperimentRunCreateParams,
  ExperimentRunCreateResponse,
  ExperimentRunCreateResponsesItemsCursorPostPagination,
  ExperimentRuns,
} from './experiment-runs.js';
import * as RunsAPI from './runs.js';
import {
  ExampleWithRunsCh,
  QueryExampleSchemaWithRuns,
  RunCreateParams,
  RunCreateResponse,
  Runs,
  SortParamsForRunsComparisonView,
} from './runs.js';
import * as ShareAPI from './share.js';
import { DatasetShareSchema, Share, ShareCreateParams, ShareDeleteAllResponse } from './share.js';
import * as SplitsAPI from './splits.js';
import {
  SplitCreateParams,
  SplitCreateResponse,
  SplitRetrieveParams,
  SplitRetrieveResponse,
  Splits,
} from './splits.js';
import * as VersionsAPI from './versions.js';
import {
  VersionListParams,
  VersionRetrieveDiffParams,
  VersionRetrieveDiffResponse,
  Versions,
} from './versions.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination.js';
import { type Uploadable } from '../../core/uploads.js';
import { RequestOptions } from '../../internal/request-options.js';
import { multipartFormRequestOptions } from '../../internal/uploads.js';
import { path } from '../../internal/utils/path.js';

export class Datasets extends APIResource {
  versions: VersionsAPI.Versions = new VersionsAPI.Versions(this._client);
  runs: RunsAPI.Runs = new RunsAPI.Runs(this._client);
  experimentRuns: ExperimentRunsAPI.ExperimentRuns = new ExperimentRunsAPI.ExperimentRuns(this._client);
  share: ShareAPI.Share = new ShareAPI.Share(this._client);
  comparative: ComparativeAPI.Comparative = new ComparativeAPI.Comparative(this._client);
  splits: SplitsAPI.Splits = new SplitsAPI.Splits(this._client);

  /**
   * Create a new dataset.
   */
  create(body: DatasetCreateParams, options?: RequestOptions): APIPromise<Dataset> {
    return this._client.post('/api/v1/datasets', { body, ...options });
  }

  /**
   * Get a specific dataset.
   */
  retrieve(datasetID: string, options?: RequestOptions): APIPromise<Dataset> {
    return this._client.get(path`/api/v1/datasets/${datasetID}`, options);
  }

  /**
   * Update a specific dataset.
   */
  update(
    datasetID: string,
    body: DatasetUpdateParams,
    options?: RequestOptions,
  ): APIPromise<DatasetUpdateResponse> {
    return this._client.patch(path`/api/v1/datasets/${datasetID}`, { body, ...options });
  }

  /**
   * Get all datasets by query params and owner.
   */
  list(
    params: DatasetListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<DatasetsOffsetPaginationTopLevelArray, Dataset> {
    const { datatype, ...query } = params ?? {};
    return this._client.getAPIList('/api/v1/datasets', OffsetPaginationTopLevelArray<Dataset>, {
      query: { data_type: datatype, ...query },
      ...options,
    });
  }

  /**
   * Delete a specific dataset.
   */
  delete(datasetID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/datasets/${datasetID}`, options);
  }

  /**
   * Clone a dataset.
   */
  clone(body: DatasetCloneParams, options?: RequestOptions): APIPromise<DatasetCloneResponse> {
    return this._client.post('/api/v1/datasets/clone', { body, ...options });
  }

  /**
   * Download a dataset as CSV format.
   */
  retrieveCsv(
    datasetID: string,
    query: DatasetRetrieveCsvParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/csv`, { query, ...options });
  }

  /**
   * Download a dataset as CSV format.
   */
  retrieveJSONL(
    datasetID: string,
    query: DatasetRetrieveJSONLParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/jsonl`, { query, ...options });
  }

  /**
   * Download a dataset as OpenAI Evals Jsonl format.
   */
  retrieveOpenAI(
    datasetID: string,
    query: DatasetRetrieveOpenAIParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/openai`, { query, ...options });
  }

  /**
   * Download a dataset as OpenAI Jsonl format.
   */
  retrieveOpenAIFt(
    datasetID: string,
    query: DatasetRetrieveOpenAIFtParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/openai_ft`, { query, ...options });
  }

  /**
   * Get dataset version by as_of or exact tag.
   */
  retrieveVersion(
    datasetID: string,
    query: DatasetRetrieveVersionParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<DatasetVersion> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/version`, { query, ...options });
  }

  /**
   * Set a tag on a dataset version.
   */
  updateTags(
    datasetID: string,
    body: DatasetUpdateTagsParams,
    options?: RequestOptions,
  ): APIPromise<DatasetVersion> {
    return this._client.put(path`/api/v1/datasets/${datasetID}/tags`, { body, ...options });
  }

  /**
   * Create a new dataset from a CSV or JSONL file.
   */
  upload(body: DatasetUploadParams, options?: RequestOptions): APIPromise<Dataset> {
    return this._client.post(
      '/api/v1/datasets/upload',
      multipartFormRequestOptions({ body, ...options }, this._client),
    );
  }
}

export type DatasetsOffsetPaginationTopLevelArray = OffsetPaginationTopLevelArray<Dataset>;

export type DatasetVersionsOffsetPaginationTopLevelArray = OffsetPaginationTopLevelArray<DatasetVersion>;

/**
 * Enum for dataset data types.
 */
export type DataType = 'kv' | 'llm' | 'chat';

/**
 * Dataset schema.
 */
export interface Dataset {
  id: string;

  modified_at: string;

  name: string;

  session_count: number;

  tenant_id: string;

  baseline_experiment_id?: string | null;

  created_at?: string;

  /**
   * Enum for dataset data types.
   */
  data_type?: DataType | null;

  description?: string | null;

  example_count?: number | null;

  externally_managed?: boolean | null;

  inputs_schema_definition?: { [key: string]: unknown } | null;

  last_session_start_time?: string | null;

  metadata?: { [key: string]: unknown } | null;

  outputs_schema_definition?: { [key: string]: unknown } | null;

  transformations?: Array<DatasetTransformation> | null;
}

export interface DatasetTransformation {
  path: Array<string>;

  /**
   * Enum for dataset transformation types. Ordering determines the order in which
   * transformations are applied if there are multiple transformations on the same
   * path.
   */
  transformation_type:
    | 'convert_to_openai_message'
    | 'convert_to_openai_tool'
    | 'remove_system_messages'
    | 'remove_extra_fields'
    | 'extract_tools_from_run';
}

/**
 * Dataset version schema.
 */
export interface DatasetVersion {
  as_of: string;

  tags?: Array<string> | null;
}

/**
 * Schema used for creating feedback without run id or session id.
 */
export interface FeedbackCreateCoreSchema {
  key: string;

  id?: string;

  comment?: string | null;

  comparative_experiment_id?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  created_at?: string;

  extra?: { [key: string]: unknown } | null;

  feedback_config?: FeedbackCreateCoreSchema.FeedbackConfig | null;

  feedback_group_id?: string | null;

  /**
   * Feedback from the LangChainPlus App.
   */
  feedback_source?:
    | FeedbackCreateCoreSchema.AppFeedbackSource
    | FeedbackCreateCoreSchema.APIFeedbackSource
    | FeedbackCreateCoreSchema.ModelFeedbackSource
    | FeedbackCreateCoreSchema.AutoEvalFeedbackSource
    | null;

  modified_at?: string;

  score?: number | boolean | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackCreateCoreSchema {
  export interface FeedbackConfig {
    /**
     * Enum for feedback types.
     */
    type: 'continuous' | 'categorical' | 'freeform';

    categories?: Array<FeedbackConfig.Category> | null;

    max?: number | null;

    min?: number | null;
  }

  export namespace FeedbackConfig {
    /**
     * Specific value and label pair for feedback
     */
    export interface Category {
      value: number;

      label?: string | null;
    }
  }

  /**
   * Feedback from the LangChainPlus App.
   */
  export interface AppFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'app';
  }

  /**
   * API feedback source.
   */
  export interface APIFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'api';
  }

  /**
   * Model feedback source.
   */
  export interface ModelFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'model';
  }

  /**
   * Auto eval feedback source.
   */
  export interface AutoEvalFeedbackSource {
    metadata?: { [key: string]: unknown } | null;

    type?: 'auto_eval';
  }
}

export interface Missing {
  __missing__: '__missing__';
}

/**
 * Enum for available dataset columns to sort by.
 */
export type SortByDatasetColumn =
  | 'name'
  | 'created_at'
  | 'last_session_start_time'
  | 'example_count'
  | 'session_count'
  | 'modified_at';

export interface DatasetUpdateResponse {
  id: string;

  name: string;

  tenant_id: string;

  created_at?: string;

  /**
   * Enum for dataset data types.
   */
  data_type?: DataType | null;

  description?: string | null;

  externally_managed?: boolean | null;

  inputs_schema_definition?: { [key: string]: unknown } | null;

  outputs_schema_definition?: { [key: string]: unknown } | null;

  transformations?: Array<DatasetTransformation> | null;
}

export type DatasetDeleteResponse = unknown;

export type DatasetCloneResponse = Array<{ [key: string]: unknown }>;

export type DatasetRetrieveCsvResponse = unknown;

export type DatasetRetrieveJSONLResponse = unknown;

export type DatasetRetrieveOpenAIResponse = unknown;

export type DatasetRetrieveOpenAIFtResponse = unknown;

export interface DatasetCreateParams {
  name: string;

  id?: string | null;

  created_at?: string;

  /**
   * Enum for dataset data types.
   */
  data_type?: DataType;

  description?: string | null;

  externally_managed?: boolean | null;

  extra?: { [key: string]: unknown } | null;

  inputs_schema_definition?: { [key: string]: unknown } | null;

  outputs_schema_definition?: { [key: string]: unknown } | null;

  tag_value_ids?: Array<string> | null;

  transformations?: Array<DatasetTransformation> | null;
}

export interface DatasetUpdateParams {
  baseline_experiment_id?: string | Missing | null;

  description?: string | Missing | null;

  inputs_schema_definition?: { [key: string]: unknown } | Missing | null;

  metadata?: { [key: string]: unknown } | Missing | null;

  name?: string | Missing | null;

  outputs_schema_definition?: { [key: string]: unknown } | Missing | null;

  patch_examples?: { [key: string]: DatasetUpdateParams.PatchExamples } | null;

  transformations?: Array<DatasetTransformation> | Missing | null;
}

export namespace DatasetUpdateParams {
  /**
   * Update class for Example.
   */
  export interface PatchExamples {
    attachments_operations?: PatchExamples.AttachmentsOperations | null;

    dataset_id?: string | null;

    inputs?: { [key: string]: unknown } | null;

    metadata?: { [key: string]: unknown } | null;

    outputs?: { [key: string]: unknown } | null;

    overwrite?: boolean;

    split?: Array<string> | string | null;
  }

  export namespace PatchExamples {
    export interface AttachmentsOperations {
      /**
       * Mapping of old attachment names to new names
       */
      rename?: { [key: string]: string };

      /**
       * List of attachment names to keep
       */
      retain?: Array<string>;
    }
  }
}

export interface DatasetListParams extends OffsetPaginationTopLevelArrayParams {
  id?: Array<string> | null;

  /**
   * Enum for dataset data types.
   */
  datatype?: Array<DataType> | DataType | null;

  exclude?: Array<'example_count'> | null;

  exclude_corrections_datasets?: boolean;

  metadata?: string | null;

  name?: string | null;

  name_contains?: string | null;

  /**
   * Enum for available dataset columns to sort by.
   */
  sort_by?: SortByDatasetColumn;

  sort_by_desc?: boolean;

  tag_value_id?: Array<string> | null;
}

export interface DatasetCloneParams {
  source_dataset_id: string;

  target_dataset_id: string;

  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: (string & {}) | string | null;

  examples?: Array<string>;

  split?: string | Array<string> | null;

  tag_value_ids?: Array<string> | null;
}

export interface DatasetRetrieveCsvParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: string | null;
}

export interface DatasetRetrieveJSONLParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: string | null;
}

export interface DatasetRetrieveOpenAIParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: string | null;
}

export interface DatasetRetrieveOpenAIFtParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: string | null;
}

export interface DatasetRetrieveVersionParams {
  as_of?: string | null;

  tag?: string | null;
}

export interface DatasetUpdateTagsParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of: (string & {}) | string;

  tag: string;
}

export interface DatasetUploadParams {
  file: Uploadable;

  input_keys: Array<string>;

  /**
   * Enum for dataset data types.
   */
  data_type?: DataType;

  description?: string | null;

  input_key_mappings?: string | null;

  inputs_schema_definition?: string | null;

  metadata_key_mappings?: string | null;

  metadata_keys?: Array<string>;

  name?: string | null;

  output_key_mappings?: string | null;

  output_keys?: Array<string>;

  outputs_schema_definition?: string | null;

  tag_value_ids?: string | null;

  transformations?: string | null;
}

Datasets.Versions = Versions;
Datasets.Runs = Runs;
Datasets.ExperimentRuns = ExperimentRuns;
Datasets.Share = Share;
Datasets.Comparative = Comparative;
Datasets.Splits = Splits;

export declare namespace Datasets {
  export {
    type DataType as DataType,
    type Dataset as Dataset,
    type DatasetTransformation as DatasetTransformation,
    type DatasetVersion as DatasetVersion,
    type FeedbackCreateCoreSchema as FeedbackCreateCoreSchema,
    type Missing as Missing,
    type SortByDatasetColumn as SortByDatasetColumn,
    type DatasetUpdateResponse as DatasetUpdateResponse,
    type DatasetDeleteResponse as DatasetDeleteResponse,
    type DatasetCloneResponse as DatasetCloneResponse,
    type DatasetRetrieveCsvResponse as DatasetRetrieveCsvResponse,
    type DatasetRetrieveJSONLResponse as DatasetRetrieveJSONLResponse,
    type DatasetRetrieveOpenAIResponse as DatasetRetrieveOpenAIResponse,
    type DatasetRetrieveOpenAIFtResponse as DatasetRetrieveOpenAIFtResponse,
    type DatasetsOffsetPaginationTopLevelArray as DatasetsOffsetPaginationTopLevelArray,
    type DatasetCreateParams as DatasetCreateParams,
    type DatasetUpdateParams as DatasetUpdateParams,
    type DatasetListParams as DatasetListParams,
    type DatasetCloneParams as DatasetCloneParams,
    type DatasetRetrieveCsvParams as DatasetRetrieveCsvParams,
    type DatasetRetrieveJSONLParams as DatasetRetrieveJSONLParams,
    type DatasetRetrieveOpenAIParams as DatasetRetrieveOpenAIParams,
    type DatasetRetrieveOpenAIFtParams as DatasetRetrieveOpenAIFtParams,
    type DatasetRetrieveVersionParams as DatasetRetrieveVersionParams,
    type DatasetUpdateTagsParams as DatasetUpdateTagsParams,
    type DatasetUploadParams as DatasetUploadParams,
  };

  export {
    Versions as Versions,
    type VersionRetrieveDiffResponse as VersionRetrieveDiffResponse,
    type VersionListParams as VersionListParams,
    type VersionRetrieveDiffParams as VersionRetrieveDiffParams,
  };

  export {
    Runs as Runs,
    type ExampleWithRunsCh as ExampleWithRunsCh,
    type QueryExampleSchemaWithRuns as QueryExampleSchemaWithRuns,
    type SortParamsForRunsComparisonView as SortParamsForRunsComparisonView,
    type RunCreateResponse as RunCreateResponse,
    type RunCreateParams as RunCreateParams,
  };

  export {
    ExperimentRuns as ExperimentRuns,
    type ExperimentRunCreateResponse as ExperimentRunCreateResponse,
    type ExperimentRunCreateResponsesItemsCursorPostPagination as ExperimentRunCreateResponsesItemsCursorPostPagination,
    type ExperimentRunCreateParams as ExperimentRunCreateParams,
  };

  export {
    Share as Share,
    type DatasetShareSchema as DatasetShareSchema,
    type ShareDeleteAllResponse as ShareDeleteAllResponse,
    type ShareCreateParams as ShareCreateParams,
  };

  export {
    Comparative as Comparative,
    type SimpleExperimentInfo as SimpleExperimentInfo,
    type SortByComparativeExperimentColumn as SortByComparativeExperimentColumn,
    type ComparativeCreateResponse as ComparativeCreateResponse,
    type ComparativeDeleteResponse as ComparativeDeleteResponse,
    type ComparativeCreateParams as ComparativeCreateParams,
  };

  export {
    Splits as Splits,
    type SplitCreateResponse as SplitCreateResponse,
    type SplitRetrieveResponse as SplitRetrieveResponse,
    type SplitCreateParams as SplitCreateParams,
    type SplitRetrieveParams as SplitRetrieveParams,
  };
}
