// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Share extends APIResource {
  /**
   * Mints a public share token for a thread. Idempotent: sharing an already-shared
   * thread returns the existing token.
   *
   * @example
   * ```ts
   * const share = await client.threads.share.create(
   *   'thread_id',
   *   { project_id: '018e4c7e-a9fb-7ef0-a5b6-6ea3a82e9327' },
   * );
   * ```
   */
  create(
    threadID: string,
    body: ShareCreateParams,
    options?: RequestOptions,
  ): APIPromise<ShareCreateResponse> {
    return this._client.post(path`/api/v2/threads/${threadID}/share`, { body, ...options });
  }

  /**
   * Returns the share token for a thread. The token is omitted when the thread is
   * not shared. Gated on runs:share so the control's state matches the control's
   * permission.
   *
   * @example
   * ```ts
   * const share = await client.threads.share.retrieve(
   *   'thread_id',
   *   { project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e' },
   * );
   * ```
   */
  retrieve(
    threadID: string,
    query: ShareRetrieveParams,
    options?: RequestOptions,
  ): APIPromise<ShareRetrieveResponse> {
    return this._client.get(path`/api/v2/threads/${threadID}/share`, { query, ...options });
  }

  /**
   * Deletes the share token for a thread. Idempotent: returns 204 whether or not a
   * share token existed. Deliberately does not verify the thread still exists.
   *
   * @example
   * ```ts
   * await client.threads.share.delete('thread_id', {
   *   project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   * });
   * ```
   */
  delete(threadID: string, params: ShareDeleteParams, options?: RequestOptions): APIPromise<void> {
    const { project_id } = params;
    return this._client.delete(path`/api/v2/threads/${threadID}/share`, {
      query: { project_id },
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface ShareCreateResponse {
  share_token?: string;
}

export interface ShareRetrieveResponse {
  share_token?: string;
}

export interface ShareCreateParams {
  /**
   * project_id is the tracing project UUID containing the thread.
   */
  project_id: string;
}

export interface ShareRetrieveParams {
  /**
   * Project UUID
   */
  project_id: string;
}

export interface ShareDeleteParams {
  /**
   * Project UUID
   */
  project_id: string;
}

export declare namespace Share {
  export {
    type ShareCreateResponse as ShareCreateResponse,
    type ShareRetrieveResponse as ShareRetrieveResponse,
    type ShareCreateParams as ShareCreateParams,
    type ShareRetrieveParams as ShareRetrieveParams,
    type ShareDeleteParams as ShareDeleteParams,
  };
}
