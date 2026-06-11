// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Validate extends APIResource {
  /**
   * Validate an example.
   */
  create(options?: RequestOptions): APIPromise<ExampleValidationResult> {
    return this._client.post('/api/v1/examples/validate', options);
  }

  /**
   * Validate examples in bulk.
   */
  bulk(options?: RequestOptions): APIPromise<ValidateBulkResponse> {
    return this._client.post('/api/v1/examples/validate/bulk', options);
  }
}

/**
 * Validation result for Example, combining fields from Create/Base/Update schemas.
 */
export interface ExampleValidationResult {
  id?: string | null;

  created_at?: string | null;

  dataset_id?: string | null;

  inputs?: { [key: string]: unknown } | null;

  metadata?: { [key: string]: unknown } | null;

  outputs?: { [key: string]: unknown } | null;

  overwrite?: boolean;

  source_run_id?: string | null;

  split?: Array<string> | string | null;

  use_source_run_io?: boolean;
}

export type ValidateBulkResponse = Array<ExampleValidationResult>;

export declare namespace Validate {
  export {
    type ExampleValidationResult as ExampleValidationResult,
    type ValidateBulkResponse as ValidateBulkResponse,
  };
}
