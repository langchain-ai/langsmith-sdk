// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Examples extends APIResource {
  /**
   * Soft-delete an example, preserving prior versions and their attachments. If the
   * latest version is already deleted, the request succeeds without creating another
   * version. Deletion is recorded at the current time or just after the latest
   * version, whichever is later. For future-dated versions, latest reads reflect
   * deletion immediately; timestamp reads reflect deletion only at or after the
   * recorded deletion timestamp.
   */
  delete(exampleID: string, params: ExampleDeleteParams, options?: RequestOptions): APIPromise<void> {
    const { dataset_id } = params;
    return this._client.delete(path`/api/v1/platform/datasets/${dataset_id}/examples/${exampleID}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface ExampleDeleteParams {
  /**
   * Dataset ID
   */
  dataset_id: string;
}

export declare namespace Examples {
  export { type ExampleDeleteParams as ExampleDeleteParams };
}
