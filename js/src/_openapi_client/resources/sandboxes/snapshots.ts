// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Snapshots extends APIResource {
  /**
   * Create a snapshot from a Docker image (async build).
   */
  create(body: SnapshotCreateParams, options?: RequestOptions): APIPromise<SnapshotCreateResponse> {
    return this._client.post('/v2/sandboxes/snapshots', { body, ...options });
  }

  /**
   * Get a sandbox snapshot by ID.
   */
  retrieve(snapshotID: string, options?: RequestOptions): APIPromise<SnapshotRetrieveResponse> {
    return this._client.get(path`/v2/sandboxes/snapshots/${snapshotID}`, options);
  }

  /**
   * List sandbox snapshots for the authenticated tenant, with optional filtering,
   * sorting, and pagination.
   */
  list(
    query: SnapshotListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<SnapshotListResponse> {
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

export interface SnapshotCreateResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  docker_image?: string;

  fs_capacity_bytes?: number;

  fs_used_bytes?: number;

  image_digest?: string;

  /**
   * MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
   * state. A non-nil value is the canonical signal that this snapshot can
   * warm-restore from memory; nil means rootfs only.
   */
  memory_snapshot_size_bytes?: number;

  name?: string;

  registry_id?: string;

  source_sandbox_id?: string;

  status?: string;

  status_message?: string;

  updated_at?: string;
}

export interface SnapshotRetrieveResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  docker_image?: string;

  fs_capacity_bytes?: number;

  fs_used_bytes?: number;

  image_digest?: string;

  /**
   * MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
   * state. A non-nil value is the canonical signal that this snapshot can
   * warm-restore from memory; nil means rootfs only.
   */
  memory_snapshot_size_bytes?: number;

  name?: string;

  registry_id?: string;

  source_sandbox_id?: string;

  status?: string;

  status_message?: string;

  updated_at?: string;
}

export interface SnapshotListResponse {
  offset?: number;

  snapshots?: Array<SnapshotListResponse.Snapshot>;
}

export namespace SnapshotListResponse {
  export interface Snapshot {
    id?: string;

    created_at?: string;

    created_by?: string;

    docker_image?: string;

    fs_capacity_bytes?: number;

    fs_used_bytes?: number;

    image_digest?: string;

    /**
     * MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
     * state. A non-nil value is the canonical signal that this snapshot can
     * warm-restore from memory; nil means rootfs only.
     */
    memory_snapshot_size_bytes?: number;

    name?: string;

    registry_id?: string;

    source_sandbox_id?: string;

    status?: string;

    status_message?: string;

    updated_at?: string;
  }
}

export interface SnapshotCreateParams {
  docker_image: string;

  fs_capacity_bytes: number;

  name: string;

  registry_id?: string;
}

export interface SnapshotListParams {
  /**
   * Filter by creator identity. Only 'me' is supported.
   */
  created_by?: string;

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
  export {
    type SnapshotCreateResponse as SnapshotCreateResponse,
    type SnapshotRetrieveResponse as SnapshotRetrieveResponse,
    type SnapshotListResponse as SnapshotListResponse,
    type SnapshotCreateParams as SnapshotCreateParams,
    type SnapshotListParams as SnapshotListParams,
  };
}
