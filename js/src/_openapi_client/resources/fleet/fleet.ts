// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ThreadsAPI from './threads.js';
import { ThreadActivateSandboxResponse, Threads } from './threads.js';

export class Fleet extends APIResource {
  threads: ThreadsAPI.Threads = new ThreadsAPI.Threads(this._client);
}

Fleet.Threads = Threads;

export declare namespace Fleet {
  export { Threads as Threads, type ThreadActivateSandboxResponse as ThreadActivateSandboxResponse };
}
