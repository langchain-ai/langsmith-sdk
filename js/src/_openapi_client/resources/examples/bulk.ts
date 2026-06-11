// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as ExamplesAPI from './examples';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';

export class Bulk extends APIResource {
  /**
   * Create bulk examples.
   */
  create(params: BulkCreateParams, options?: RequestOptions): APIPromise<BulkCreateResponse> {
    const { body } = params;
    return this._client.post('/api/v1/examples/bulk', { body: body, ...options });
  }

  /**
   * Legacy update examples in bulk. For update involving attachments, use PATCH
   * /v1/platform/datasets/{dataset_id}/examples instead.
   */
  patchAll(params: BulkPatchAllParams, options?: RequestOptions): APIPromise<unknown> {
    const { body } = params;
    return this._client.patch('/api/v1/examples/bulk', { body: body, ...options });
  }
}

export type BulkCreateResponse = Array<ExamplesAPI.Example>;

export type BulkPatchAllResponse = unknown;

export interface BulkCreateParams {
  /**
   * Schema for a batch of examples to be created.
   */
  body: Array<BulkCreateParams.Body>;
}

export namespace BulkCreateParams {
  /**
   * Example with optional created_at to prevent duplicate versions in bulk
   * operations.
   */
  export interface Body {
    dataset_id: string;

    id?: string | null;

    created_at?: string | null;

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
}

export interface BulkPatchAllParams {
  body: Array<BulkPatchAllParams.Body>;
}

export namespace BulkPatchAllParams {
  /**
   * Bulk update class for Example (includes example id).
   */
  export interface Body {
    id: string;

    attachments_operations?: ExamplesAPI.AttachmentsOperations | null;

    dataset_id?: string | null;

    inputs?: { [key: string]: unknown } | null;

    metadata?: { [key: string]: unknown } | null;

    outputs?: { [key: string]: unknown } | null;

    overwrite?: boolean;

    split?: Array<string> | string | null;
  }
}

export declare namespace Bulk {
  export {
    type BulkCreateResponse as BulkCreateResponse,
    type BulkPatchAllResponse as BulkPatchAllResponse,
    type BulkCreateParams as BulkCreateParams,
    type BulkPatchAllParams as BulkPatchAllParams,
  };
}
