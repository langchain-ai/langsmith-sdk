// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as CommitsAPI from '../commits';
import * as DirectoriesAPI from './directories';
import {
  Directories,
  DirectoryCommitParams,
  DirectoryCommitResponse,
  DirectoryDeleteParams,
  DirectoryListParams,
  DirectoryListResponse,
} from './directories';
import { APIPromise } from '../../core/api-promise';
import { OffsetPaginationRepos, type OffsetPaginationReposParams, PagePromise } from '../../core/pagination';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Repos extends APIResource {
  directories: DirectoriesAPI.Directories = new DirectoriesAPI.Directories(this._client);

  /**
   * Create a repo.
   */
  create(body: RepoCreateParams, options?: RequestOptions): APIPromise<CreateRepoResponse> {
    return this._client.post('/api/v1/repos', { body, ...options });
  }

  /**
   * Get a repo.
   */
  retrieve(repo: string, params: RepoRetrieveParams, options?: RequestOptions): APIPromise<GetRepoResponse> {
    const { owner } = params;
    return this._client.get(path`/api/v1/repos/${owner}/${repo}`, options);
  }

  /**
   * Update a repo.
   */
  update(repo: string, params: RepoUpdateParams, options?: RequestOptions): APIPromise<CreateRepoResponse> {
    const { owner, ...body } = params;
    return this._client.patch(path`/api/v1/repos/${owner}/${repo}`, { body, ...options });
  }

  /**
   * Get all repos.
   */
  list(
    params: RepoListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<RepoWithLookupsOffsetPaginationRepos, RepoWithLookups> {
    const { single_repo_type, ...query } = params ?? {};
    return this._client.getAPIList('/api/v1/repos', OffsetPaginationRepos<RepoWithLookups>, {
      query: { repo_type: single_repo_type, ...query },
      ...options,
    });
  }

  /**
   * Delete a repo.
   */
  delete(repo: string, params: RepoDeleteParams, options?: RequestOptions): APIPromise<unknown> {
    const { owner } = params;
    return this._client.delete(path`/api/v1/repos/${owner}/${repo}`, options);
  }
}

export type RepoWithLookupsOffsetPaginationRepos = OffsetPaginationRepos<RepoWithLookups>;

export interface CreateRepoResponse {
  /**
   * All database fields for repos, plus helpful computed fields.
   */
  repo: RepoWithLookups;
}

export interface DemoConfig {
  examples: Array<{ [key: string]: unknown }>;

  message_index: number;

  metaprompt: { [key: string]: unknown };

  overall_feedback: string | null;
}

export type EPromptOptimizationAlgorithm = 'promptim' | 'demo';

export interface GetRepoResponse {
  /**
   * All database fields for repos, plus helpful computed fields.
   */
  repo: RepoWithLookups;
}

export interface PromptimConfig {
  auto_commit: boolean;

  dataset_name: string;

  dev_split: string | null;

  evaluators: Array<string>;

  message_index: number;

  num_epochs: number;

  task_description: string;

  test_split: string | null;

  train_split: string | null;
}

/**
 * All database fields for repos, plus helpful computed fields.
 */
export interface RepoWithLookups {
  id: string;

  created_at: string;

  full_name: string;

  is_archived: boolean;

  is_public: boolean;

  num_commits: number;

  num_downloads: number;

  num_likes: number;

  num_views: number;

  owner: string | null;

  repo_handle: string;

  repo_type: 'prompt' | 'file' | 'agent' | 'skill';

  tags: Array<string>;

  tenant_id: string;

  updated_at: string;

  commit_tags?: Array<string>;

  created_by?: string | null;

  description?: string | null;

  last_commit_hash?: string | null;

  /**
   * Response model for get_commit_manifest.
   */
  latest_commit_manifest?: CommitsAPI.CommitManifestResponse | null;

  liked_by_auth_user?: boolean | null;

  original_repo_full_name?: string | null;

  original_repo_id?: string | null;

  owners?: Array<RepoWithLookups.Owner> | null;

  readme?: string | null;

  restricted_mode?: boolean;

  source?: 'internal' | 'external' | null;

  upstream_repo_full_name?: string | null;

  upstream_repo_id?: string | null;
}

export namespace RepoWithLookups {
  /**
   * A repo owner with user details.
   *
   * Note: identity_id and email may be None when returned to users outside the
   * repo's tenant (PII protection).
   */
  export interface Owner {
    created_at: string;

    email: string | null;

    full_name: string | null;

    identity_id: string | null;

    ls_user_id: string;
  }
}

export type RepoDeleteResponse = unknown;

export interface RepoCreateParams {
  is_public: boolean;

  repo_handle: string;

  description?: string | null;

  readme?: string | null;

  repo_type?: 'prompt' | 'file' | 'agent' | 'skill';

  restricted_mode?: boolean | null;

  source?: 'internal' | 'external' | null;

  tag_value_ids?: Array<string> | null;

  tags?: Array<string> | null;
}

export interface RepoRetrieveParams {
  owner: string;
}

export interface RepoUpdateParams {
  /**
   * Path param
   */
  owner: string;

  /**
   * Body param
   */
  description?: string | null;

  /**
   * Body param
   */
  is_archived?: boolean | null;

  /**
   * Body param
   */
  is_public?: boolean | null;

  /**
   * Body param
   */
  readme?: string | null;

  /**
   * Body param
   */
  restricted_mode?: boolean | null;

  /**
   * Body param
   */
  tags?: Array<string> | null;
}

export interface RepoListParams extends OffsetPaginationReposParams {
  has_commits?: boolean | null;

  include_owners?: boolean;

  is_archived?: 'true' | 'allow' | 'false' | null;

  is_public?: 'true' | 'false' | null;

  query?: string | null;

  single_repo_type?: 'prompt' | 'file' | 'agent' | 'skill' | null;

  repo_types?: Array<'prompt' | 'file' | 'agent' | 'skill'> | null;

  sort_direction?: 'asc' | 'desc' | null;

  sort_field?: 'num_likes' | 'num_downloads' | 'num_views' | 'updated_at' | 'relevance' | null;

  source?: 'internal' | 'external' | null;

  tag_value_id?: Array<string> | null;

  tags?: Array<string> | null;

  tenant_handle?: string | null;

  tenant_id?: string | null;

  upstream_repo_handle?: string | null;

  upstream_repo_owner?: string | null;

  with_latest_manifest?: boolean;
}

export interface RepoDeleteParams {
  owner: string;
}

Repos.Directories = Directories;

export declare namespace Repos {
  export {
    type CreateRepoResponse as CreateRepoResponse,
    type DemoConfig as DemoConfig,
    type EPromptOptimizationAlgorithm as EPromptOptimizationAlgorithm,
    type GetRepoResponse as GetRepoResponse,
    type PromptimConfig as PromptimConfig,
    type RepoWithLookups as RepoWithLookups,
    type RepoDeleteResponse as RepoDeleteResponse,
    type RepoWithLookupsOffsetPaginationRepos as RepoWithLookupsOffsetPaginationRepos,
    type RepoCreateParams as RepoCreateParams,
    type RepoRetrieveParams as RepoRetrieveParams,
    type RepoUpdateParams as RepoUpdateParams,
    type RepoListParams as RepoListParams,
    type RepoDeleteParams as RepoDeleteParams,
  };

  export {
    Directories as Directories,
    type DirectoryListResponse as DirectoryListResponse,
    type DirectoryCommitResponse as DirectoryCommitResponse,
    type DirectoryListParams as DirectoryListParams,
    type DirectoryDeleteParams as DirectoryDeleteParams,
    type DirectoryCommitParams as DirectoryCommitParams,
  };
}
