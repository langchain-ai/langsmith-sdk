// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Directories extends APIResource {
  /**
   * Resolves the flattened file tree for an agent or skill repository at a specific
   * commit, tag, or latest.
   */
  list(
    repo: string,
    params: DirectoryListParams,
    options?: RequestOptions,
  ): APIPromise<DirectoryListResponse> {
    const { owner, ...query } = params;
    return this._client.get(path`/v1/platform/hub/repos/${owner}/${repo}/directories`, { query, ...options });
  }

  /**
   * Deletes an agent or skill repository and its owned child file repositories.
   */
  delete(repo: string, params: DirectoryDeleteParams, options?: RequestOptions): APIPromise<void> {
    const { owner } = params;
    return this._client.delete(path`/v1/platform/hub/repos/${owner}/${repo}/directories`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }

  /**
   * Creates a new directory commit for an agent or skill repository by applying
   * file/link create, update, and delete operations.
   */
  commit(
    repo: string,
    params: DirectoryCommitParams,
    options?: RequestOptions,
  ): APIPromise<DirectoryCommitResponse> {
    const { owner, ...body } = params;
    return this._client.post(path`/v1/platform/hub/repos/${owner}/${repo}/directories/commits`, {
      body,
      ...options,
    });
  }
}

export interface DirectoryListResponse {
  commit_hash?: string;

  commit_id?: string;

  files?: { [key: string]: unknown };
}

export interface DirectoryCommitResponse {
  commit?: DirectoryCommitResponse.Commit;
}

export namespace DirectoryCommitResponse {
  export interface Commit {
    id?: string;

    commit_hash?: string;

    created_at?: string;
  }
}

export interface DirectoryListParams {
  /**
   * Path param: Repository owner handle or '-' for current tenant
   */
  owner: string;

  /**
   * Query param: Commit hash/tag to resolve (defaults to latest)
   */
  commit?: string;
}

export interface DirectoryDeleteParams {
  /**
   * Repository owner handle or '-' for current tenant
   */
  owner: string;
}

export interface DirectoryCommitParams {
  /**
   * Path param: Repository owner handle or '-' for current tenant
   */
  owner: string;

  /**
   * Body param: Files maps path to an Entry (object = create/update/link, null =
   * delete/unlink).
   */
  files?: { [key: string]: unknown };

  /**
   * Body param
   */
  parent_commit?: string;
}

export declare namespace Directories {
  export {
    type DirectoryListResponse as DirectoryListResponse,
    type DirectoryCommitResponse as DirectoryCommitResponse,
    type DirectoryListParams as DirectoryListParams,
    type DirectoryDeleteParams as DirectoryDeleteParams,
    type DirectoryCommitParams as DirectoryCommitParams,
  };
}
