// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';

export class Configs extends APIResource {
  /**
   * Soft delete a feedback config by marking it as deleted.
   *
   * The config can be recreated later with the same key (simple reuse pattern).
   * Existing feedback records with this key will remain unchanged.
   */
  delete(params: ConfigDeleteParams, options?: RequestOptions): APIPromise<void> {
    const { feedback_key } = params;
    return this._client.delete('/api/v1/feedback-configs', {
      query: { feedback_key },
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface ConfigDeleteParams {
  feedback_key: string;
}

export declare namespace Configs {
  export { type ConfigDeleteParams as ConfigDeleteParams };
}
