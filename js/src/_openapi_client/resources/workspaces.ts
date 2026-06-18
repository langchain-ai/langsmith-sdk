// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class Workspaces extends APIResource {
  /**
   * Create a new workspace.
   */
  create(body: WorkspaceCreateParams, options?: RequestOptions): APIPromise<WorkspaceCreateResponse> {
    return this._client.post('/api/v1/workspaces', { body, ...options });
  }

  /**
   * Update a workspace.
   */
  update(
    workspaceID: string,
    body: WorkspaceUpdateParams,
    options?: RequestOptions,
  ): APIPromise<WorkspaceUpdateResponse> {
    return this._client.patch(path`/api/v1/workspaces/${workspaceID}`, { body, ...options });
  }

  /**
   * Get all workspaces visible to this auth in the current org. Does not create a
   * new workspace/org.
   */
  list(
    query: WorkspaceListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<WorkspaceListResponse> {
    return this._client.get('/api/v1/workspaces', { query, ...options });
  }

  /**
   * Delete Workspace
   */
  delete(workspaceID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/workspaces/${workspaceID}`, options);
  }
}

/**
 * Tenant schema.
 */
export interface WorkspaceCreateResponse {
  id: string;

  created_at: string;

  display_name: string;

  is_deleted: boolean;

  is_personal: boolean;

  data_plane_url?: string | null;

  organization_id?: string | null;

  tenant_handle?: string | null;
}

/**
 * Tenant schema.
 */
export interface WorkspaceUpdateResponse {
  id: string;

  created_at: string;

  display_name: string;

  is_deleted: boolean;

  is_personal: boolean;

  data_plane_url?: string | null;

  organization_id?: string | null;

  tenant_handle?: string | null;
}

export type WorkspaceListResponse = Array<WorkspaceListResponse.WorkspaceListResponseItem>;

export namespace WorkspaceListResponse {
  export interface WorkspaceListResponseItem {
    id: string;

    created_at: string;

    display_name: string;

    is_deleted: boolean;

    is_personal: boolean;

    data_plane_url?: string | null;

    organization_id?: string | null;

    permissions?: Array<string> | null;

    /**
     * @deprecated
     */
    read_only?: boolean;

    role_id?: string | null;

    role_name?: string | null;

    tenant_handle?: string | null;
  }
}

export type WorkspaceDeleteResponse = unknown;

export interface WorkspaceCreateParams {
  display_name: string;

  id?: string;

  tenant_handle?: string | null;
}

export interface WorkspaceUpdateParams {
  display_name: string;
}

export interface WorkspaceListParams {
  data_plane_id?: string | null;

  include_deleted?: boolean;
}

export declare namespace Workspaces {
  export {
    type WorkspaceCreateResponse as WorkspaceCreateResponse,
    type WorkspaceUpdateResponse as WorkspaceUpdateResponse,
    type WorkspaceListResponse as WorkspaceListResponse,
    type WorkspaceDeleteResponse as WorkspaceDeleteResponse,
    type WorkspaceCreateParams as WorkspaceCreateParams,
    type WorkspaceUpdateParams as WorkspaceUpdateParams,
    type WorkspaceListParams as WorkspaceListParams,
  };
}
