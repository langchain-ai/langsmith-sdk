// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as SandboxesAPI from './sandboxes.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Snapshots extends APIResource {
  /**
   * Create a snapshot from a Docker image (async build).
   */
  create(body: SnapshotCreateParams, options?: RequestOptions): APIPromise<SandboxesAPI.SnapshotResponse> {
    return this._client.post('/v2/sandboxes/snapshots', { body, ...options });
  }

  /**
   * Get a sandbox snapshot by ID.
   */
  retrieve(snapshotID: string, options?: RequestOptions): APIPromise<SandboxesAPI.SnapshotResponse> {
    return this._client.get(path`/v2/sandboxes/snapshots/${snapshotID}`, options);
  }

  /**
   * List sandbox snapshots for the authenticated tenant, with optional filtering,
   * sorting, and pagination.
   */
  list(
    query: SnapshotListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<SandboxesAPI.SnapshotListResponse> {
    return this._client.get('/v2/sandboxes/snapshots', { query, ...options });
  }

  /**
   * Delete a snapshot by ID. The underlying storage is reclaimed asynchronously.
   */
  delete(snapshotID: string, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/v2/sandboxes/snapshots/${snapshotID}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface SnapshotCreateParams {
  docker_image: string;

  fs_capacity_bytes: number;

  name: string;

  /**
   * Labels seed the snapshot's labels, overriding any label of the same key derived
   * from the Docker image.
   */
  labels?: { [key: string]: string };

  registry_id?: string;
}

export interface SnapshotListParams {
  /**
   * Filter by creator identity. Only 'me' is supported.
   */
  created_by?: string;

  /**
   * Filter by label. Repeatable; all must match. Use 'key' to match on key presence
   * or 'key=value' for equality.
   */
  label?: Array<string>;

  /**
   * Maximum number of results
   */
  limit?: number;

  /**
   * Filter by name substring
   */
  name_contains?: string;

  /**
   * Pagination offset
   */
  offset?: number;

  /**
   * Sort column (name, status, created_at)
   */
  sort_by?: string;

  /**
   * Sort direction (asc, desc)
   */
  sort_direction?: string;

  /**
   * Filter by status (building, ready, failed, deleting)
   */
  status?: string;
}

export declare namespace Snapshots {
  export { type SnapshotCreateParams as SnapshotCreateParams, type SnapshotListParams as SnapshotListParams };
}
