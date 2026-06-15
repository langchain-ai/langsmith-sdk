// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as BulkAPI from './bulk.js';
import { Bulk, BulkCreateParams, BulkCreateResponse, BulkPatchAllParams, BulkPatchAllResponse } from './bulk.js';
import * as ValidateAPI from './validate.js';
import { ExampleValidationResult, Validate, ValidateBulkResponse } from './validate.js';
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

export class Examples extends APIResource {
  bulk: BulkAPI.Bulk = new BulkAPI.Bulk(this._client);
  validate: ValidateAPI.Validate = new ValidateAPI.Validate(this._client);

  /**
   * Create a new example.
   */
  create(body: ExampleCreateParams, options?: RequestOptions): APIPromise<Example> {
    return this._client.post('/api/v1/examples', { body, ...options });
  }

  /**
   * Get a specific example.
   */
  retrieve(
    exampleID: string,
    query: ExampleRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<Example> {
    return this._client.get(path`/api/v1/examples/${exampleID}`, { query, ...options });
  }

  /**
   * Update a specific example.
   */
  update(exampleID: string, body: ExampleUpdateParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.patch(path`/api/v1/examples/${exampleID}`, { body, ...options });
  }

  /**
   * Get all examples by query params
   */
  list(
    query: ExampleListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<ExamplesOffsetPaginationTopLevelArray, Example> {
    return this._client.getAPIList('/api/v1/examples', OffsetPaginationTopLevelArray<Example>, {
      query,
      ...options,
    });
  }

  /**
   * Soft delete an example. Only deletes the example in the 'latest' version of the
   * dataset.
   */
  delete(exampleID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/examples/${exampleID}`, options);
  }

  /**
   * Soft delete examples. Only deletes the examples in the 'latest' version of the
   * dataset.
   */
  deleteAll(params: ExampleDeleteAllParams, options?: RequestOptions): APIPromise<unknown> {
    const { example_ids } = params;
    return this._client.delete('/api/v1/examples', { query: { example_ids }, ...options });
  }

  /**
   * Count all examples by query params
   */
  retrieveCount(
    query: ExampleRetrieveCountParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<ExampleRetrieveCountResponse> {
    return this._client.get('/api/v1/examples/count', { query, ...options });
  }

  /**
   * Upload examples from a CSV file.
   *
   * Note: For non-csv upload, please use the POST
   * /v1/platform/datasets/{dataset_id}/examples endpoint which provides more
   * efficient upload.
   */
  uploadFromCsv(
    datasetID: string,
    body: ExampleUploadFromCsvParams,
    options?: RequestOptions,
  ): APIPromise<ExampleUploadFromCsvResponse> {
    return this._client.post(
      path`/api/v1/examples/upload/${datasetID}`,
      multipartFormRequestOptions({ body, ...options }, this._client),
    );
  }
}

export type ExamplesOffsetPaginationTopLevelArray = OffsetPaginationTopLevelArray<Example>;

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

/**
 * Example schema.
 */
export interface Example {
  id: string;

  dataset_id: string;

  inputs: { [key: string]: unknown };

  name: string;

  attachment_urls?: { [key: string]: unknown } | null;

  created_at?: string;

  metadata?: { [key: string]: unknown } | null;

  modified_at?: string | null;

  outputs?: { [key: string]: unknown } | null;

  source_run_id?: string | null;
}

export type ExampleSelect =
  | 'id'
  | 'created_at'
  | 'modified_at'
  | 'name'
  | 'dataset_id'
  | 'source_run_id'
  | 'metadata'
  | 'inputs'
  | 'outputs'
  | 'attachment_urls';

export type ExampleUpdateResponse = unknown;

export type ExampleDeleteResponse = unknown;

export type ExampleDeleteAllResponse = unknown;

export type ExampleRetrieveCountResponse = number;

export type ExampleUploadFromCsvResponse = Array<Example>;

export interface ExampleCreateParams {
  dataset_id: string;

  id?: string | null;

  created_at?: string;

  inputs?: { [key: string]: unknown } | null;

  metadata?: { [key: string]: unknown } | null;

  outputs?: { [key: string]: unknown } | null;

  source_run_id?: string | null;

  split?: Array<string> | string | null;

  /**
   * Use Legacy Message Format for LLM runs
   */
  use_legacy_message_format?: boolean;

  use_source_run_attachments?: Array<string>;

  use_source_run_io?: boolean;
}

export interface ExampleRetrieveParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: (string & {}) | string;

  dataset?: string | null;
}

export interface ExampleUpdateParams {
  attachments_operations?: AttachmentsOperations | null;

  dataset_id?: string | null;

  inputs?: { [key: string]: unknown } | null;

  metadata?: { [key: string]: unknown } | null;

  outputs?: { [key: string]: unknown } | null;

  overwrite?: boolean;

  split?: Array<string> | string | null;
}

export interface ExampleListParams extends OffsetPaginationTopLevelArrayParams {
  id?: Array<string> | null;

  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: (string & {}) | string;

  dataset?: string | null;

  descending?: boolean | null;

  filter?: string | null;

  full_text_contains?: Array<string> | null;

  metadata?: string | null;

  order?: 'recent' | 'random' | 'recently_created' | 'id';

  random_seed?: number | null;

  select?: Array<ExampleSelect>;

  splits?: Array<string> | null;
}

export interface ExampleDeleteAllParams {
  example_ids: Array<string>;
}

export interface ExampleRetrieveCountParams {
  id?: Array<string> | null;

  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: (string & {}) | string;

  dataset?: string | null;

  filter?: string | null;

  full_text_contains?: Array<string> | null;

  metadata?: string | null;

  splits?: Array<string> | null;
}

export interface ExampleUploadFromCsvParams {
  file: Uploadable;

  input_keys: Array<string>;

  metadata_keys?: Array<string>;

  output_keys?: Array<string>;
}

Examples.Bulk = Bulk;
Examples.Validate = Validate;

export declare namespace Examples {
  export {
    type AttachmentsOperations as AttachmentsOperations,
    type Example as Example,
    type ExampleSelect as ExampleSelect,
    type ExampleUpdateResponse as ExampleUpdateResponse,
    type ExampleDeleteResponse as ExampleDeleteResponse,
    type ExampleDeleteAllResponse as ExampleDeleteAllResponse,
    type ExampleRetrieveCountResponse as ExampleRetrieveCountResponse,
    type ExampleUploadFromCsvResponse as ExampleUploadFromCsvResponse,
    type ExamplesOffsetPaginationTopLevelArray as ExamplesOffsetPaginationTopLevelArray,
    type ExampleCreateParams as ExampleCreateParams,
    type ExampleRetrieveParams as ExampleRetrieveParams,
    type ExampleUpdateParams as ExampleUpdateParams,
    type ExampleListParams as ExampleListParams,
    type ExampleDeleteAllParams as ExampleDeleteAllParams,
    type ExampleRetrieveCountParams as ExampleRetrieveCountParams,
    type ExampleUploadFromCsvParams as ExampleUploadFromCsvParams,
  };

  export {
    Bulk as Bulk,
    type BulkCreateResponse as BulkCreateResponse,
    type BulkPatchAllResponse as BulkPatchAllResponse,
    type BulkCreateParams as BulkCreateParams,
    type BulkPatchAllParams as BulkPatchAllParams,
  };

  export {
    Validate as Validate,
    type ExampleValidationResult as ExampleValidationResult,
    type ValidateBulkResponse as ValidateBulkResponse,
  };
}
