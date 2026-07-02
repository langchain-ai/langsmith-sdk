// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Registries extends APIResource {
  /**
   * Create a sandbox registry for pulling private images.
   */
  create(body: RegistryCreateParams, options?: RequestOptions): APIPromise<RegistryResponse> {
    return this._client.post('/v2/sandboxes/registries', { body, ...options });
  }

  /**
   * Get a sandbox registry by name.
   */
  retrieve(name: string, options?: RequestOptions): APIPromise<RegistryResponse> {
    return this._client.get(path`/v2/sandboxes/registries/${name}`, options);
  }

  /**
   * Update a sandbox registry's name and/or credentials.
   */
  update(name: string, body: RegistryUpdateParams, options?: RequestOptions): APIPromise<RegistryResponse> {
    return this._client.patch(path`/v2/sandboxes/registries/${name}`, { body, ...options });
  }

  /**
   * List sandbox registries for pulling private images.
   */
  list(
    query: RegistryListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<RegistryListResponse> {
    return this._client.get('/v2/sandboxes/registries', { query, ...options });
  }

  /**
   * Delete a sandbox registry by name.
   */
  delete(name: string, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/v2/sandboxes/registries/${name}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface RegistryListResponse {
  offset?: number;

  registries?: Array<RegistryResponse>;
}

export interface RegistryResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  name?: string;

  updated_at?: string;

  updated_by?: string;

  url?: string;
}

export interface RegistryCreateParams {
  name: string;

  password: string;

  url: string;

  username: string;
}

export interface RegistryUpdateParams {
  name?: string;

  password?: string;

  url?: string;

  username?: string;
}

export interface RegistryListParams {
  /**
   * Maximum number of registries to return
   */
  limit?: number;

  /**
   * Filter to registries whose name contains this substring
   */
  name_contains?: string;

  /**
   * Number of registries to skip
   */
  offset?: number;
}

export declare namespace Registries {
  export {
    type RegistryListResponse as RegistryListResponse,
    type RegistryResponse as RegistryResponse,
    type RegistryCreateParams as RegistryCreateParams,
    type RegistryUpdateParams as RegistryUpdateParams,
    type RegistryListParams as RegistryListParams,
  };
}
