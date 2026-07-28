// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Share extends APIResource {
  /**
   * Creates or returns a share token for a run. Child runs share their trace root.
   *
   * @example
   * ```ts
   * const share = await client.runs.share.create(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   * );
   * ```
   */
  create(runID: string, body: ShareCreateParams, options?: RequestOptions): APIPromise<ShareCreateResponse> {
    return this._client.post(path`/v2/runs/${runID}/share`, { body, ...options });
  }

  /**
   * Deletes the share token for the trace identified by trace_id and session_id.
   * Idempotent: returns 204 whether or not a share token existed.
   *
   * @example
   * ```ts
   * await client.runs.share.delete(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   * );
   * ```
   */
  delete(traceID: string, body: ShareDeleteParams, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/v2/runs/${traceID}/share`, {
      body,
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface ShareCreateResponse {
  share_token?: string;
}

export interface ShareCreateParams {
  /**
   * session_id is the tracing project UUID containing the trace.
   */
  session_id?: string;

  /**
   * trace_id is the root trace UUID to share.
   */
  trace_id?: string;
}

export interface ShareDeleteParams {
  /**
   * session_id is the tracing project UUID containing the trace.
   */
  session_id?: string;
}

export declare namespace Share {
  export {
    type ShareCreateResponse as ShareCreateResponse,
    type ShareCreateParams as ShareCreateParams,
    type ShareDeleteParams as ShareDeleteParams,
  };
}
