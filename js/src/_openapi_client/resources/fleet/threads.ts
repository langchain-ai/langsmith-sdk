// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Threads extends APIResource {
  /**
   * Starts or resumes the sandbox referenced by the thread and returns when it is
   * ready. The operation is idempotent. The thread must include
   * sandbox.sandbox_slug.
   */
  activateSandbox(threadID: string, options?: RequestOptions): APIPromise<ThreadActivateSandboxResponse> {
    return this._client.post(path`/v1/fleet/threads/${threadID}/sandbox-activation`, options);
  }
}

export interface ThreadActivateSandboxResponse {
  sandbox_slug: string;

  scope: 'agent' | 'thread';

  status: 'provisioning' | 'ready' | 'failed' | 'stopped' | 'deleting';
}

export declare namespace Threads {
  export { type ThreadActivateSandboxResponse as ThreadActivateSandboxResponse };
}
