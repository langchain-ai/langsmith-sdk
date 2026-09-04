// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as SandboxesAPI from './sandboxes.js';
import { SnapshotResponsesItemsCursorGetPagination } from './sandboxes.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  ItemsCursorGetPagination,
  type ItemsCursorGetPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Snapshots extends APIResource {
  /**
   * Create a snapshot from a Docker image (async build).
   */
  create(body: SnapshotCreateParams, options?: RequestOptions): APIPromise<SandboxesAPI.SnapshotResponse> {
    return this._client.post('/api/v2/sandboxes/snapshots', { body, ...options });
  }

  /**
   * Get a sandbox snapshot by ID or by a Docker-style reference. A bare name means
   * name:latest, falling back to the newest ready untagged snapshot of that name. To
   * list the tags under a name, use /api/v2/sandboxes/snapshots-by-name/{name}.
   */
  retrieve(snapshotID: string, options?: RequestOptions): APIPromise<SandboxesAPI.SnapshotResponse> {
    return this._client.get(path`/api/v2/sandboxes/snapshots/${snapshotID}`, options);
  }

  /**
   * List sandbox snapshots for the authenticated tenant, with optional filtering,
   * sorting, and pagination. Page with page_size and cursor: replay the response's
   * next_cursor until it comes back null, which is the only signal that no pages
   * remain. Cursors are opaque and only valid on this endpoint; do not parse or
   * construct one.
   */
  list(
    query: SnapshotListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<SnapshotResponsesItemsCursorGetPagination, SandboxesAPI.SnapshotResponse> {
    return this._client.getAPIList(
      '/api/v2/sandboxes/snapshots',
      ItemsCursorGetPagination<SandboxesAPI.SnapshotResponse>,
      { query, ...options },
    );
  }

  /**
   * Delete a snapshot by ID or by a Docker-style name[:tag] reference. The
   * underlying storage is reclaimed asynchronously.
   */
  delete(snapshotID: string, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/api/v2/sandboxes/snapshots/${snapshotID}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }

  /**
   * Get a snapshot name and every tag under it, with the snapshot each tag resolves
   * to. To fetch one snapshot, use /api/v2/sandboxes/snapshots/{snapshot_id}.
   */
  retrieveByName(name: string, options?: RequestOptions): APIPromise<SnapshotRetrieveByNameResponse> {
    return this._client.get(path`/api/v2/sandboxes/snapshots-by-name/${name}`, options);
  }
}

export interface SnapshotRetrieveByNameResponse {
  name?: string;

  tags?: Array<SnapshotRetrieveByNameResponse.Tag>;
}

export namespace SnapshotRetrieveByNameResponse {
  export interface Tag {
    snapshot_id?: string;

    tag?: string;
  }
}

export interface SnapshotCreateParams {
  docker_image: string;

  fs_capacity_bytes: number;

  name: string;

  /**
   * Description says what this snapshot's image can do, so a caller can hand it to
   * an agent as a capability summary. At most 1024 characters.
   */
  description?: string;

  /**
   * Labels seed the snapshot's labels, overriding any label of the same key derived
   * from the Docker image.
   */
  labels?: { [key: string]: string };

  registry_id?: string;

  /**
   * mutable Docker-style tag; defaults to "latest"
   */
  tag?: string;
}

export interface SnapshotListParams extends ItemsCursorGetPaginationParams {
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
   * Deprecated: use page_size. Maximum number of results
   */
  limit?: number;

  /**
   * Filter by name substring
   */
  name_contains?: string;

  /**
   * Deprecated: use cursor. Pagination offset
   */
  offset?: number;

  /**
   * Sort column (name, status, created_at)
   */
  sort_by?: string;

  /**
   * Deprecated: use sort_order. Sort direction (asc, desc)
   */
  sort_direction?: string;

  /**
   * Sort direction (asc, desc)
   */
  sort_order?: string;

  /**
   * Filter by status (building, ready, failed, deleting)
   */
  status?: string;
}

export declare namespace Snapshots {
  export {
    type SnapshotRetrieveByNameResponse as SnapshotRetrieveByNameResponse,
    type SnapshotCreateParams as SnapshotCreateParams,
    type SnapshotListParams as SnapshotListParams,
  };
}

export { type SnapshotResponsesItemsCursorGetPagination };
