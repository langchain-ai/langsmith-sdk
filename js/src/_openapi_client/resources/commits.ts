// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { OffsetPaginationCommits, type OffsetPaginationCommitsParams, PagePromise } from '../core/pagination.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class Commits extends APIResource {
  /**
   * Creates a new commit in a repository. Requires authentication and write access
   * to the repository.
   */
  create(
    repo: string,
    params: CommitCreateParams,
    options?: RequestOptions,
  ): APIPromise<CommitCreateResponse> {
    const { owner, ...body } = params;
    return this._client.post(path`/commits/${owner}/${repo}`, { body, ...options });
  }

  /**
   * Retrieves a specific commit by hash, tag, or "latest" for a repository. This
   * endpoint supports both authenticated and unauthenticated access. Authenticated
   * users can access private repos, while unauthenticated users can only access
   * public repos. Commit resolution logic:
   *
   * - "latest" or empty: Get the most recent commit
   * - Less than 8 characters: Only check for tags
   * - 8 or more characters: Prioritize commit hash over tag, check both
   */
  retrieve(
    commit: string,
    params: CommitRetrieveParams,
    options?: RequestOptions,
  ): APIPromise<CommitRetrieveResponse> {
    const { owner, repo, ...query } = params;
    return this._client.get(path`/commits/${owner}/${repo}/${commit}`, { query, ...options });
  }

  /**
   * Lists all commits for a repository with pagination support. This endpoint
   * supports both authenticated and unauthenticated access. Authenticated users can
   * access private repos, while unauthenticated users can only access public repos.
   * The include_stats parameter controls whether download and view statistics are
   * computed (defaults to true).
   */
  list(
    repo: string,
    params: CommitListParams,
    options?: RequestOptions,
  ): PagePromise<CommitWithLookupsOffsetPaginationCommits, CommitWithLookups> {
    const { owner, ...query } = params;
    return this._client.getAPIList(
      path`/commits/${owner}/${repo}`,
      OffsetPaginationCommits<CommitWithLookups>,
      { query, ...options },
    );
  }
}

export type CommitWithLookupsOffsetPaginationCommits = OffsetPaginationCommits<CommitWithLookups>;

/**
 * Response model for get_commit_manifest.
 */
export interface CommitManifestResponse {
  commit_hash: string;

  manifest: { [key: string]: unknown };

  examples?: Array<CommitManifestResponse.Example> | null;
}

export namespace CommitManifestResponse {
  /**
   * Response model for example runs
   */
  export interface Example {
    id: string;

    session_id: string;

    inputs?: { [key: string]: unknown } | null;

    outputs?: { [key: string]: unknown } | null;

    start_time?: string | null;
  }
}

export interface CommitWithLookups {
  /**
   * The commit ID
   */
  id?: string;

  /**
   * The hash of the commit
   */
  commit_hash?: string;

  /**
   * When the commit was created
   */
  created_at?: string;

  /**
   * Optional human-readable description for the commit
   */
  description?: string;

  /**
   * Example run IDs associated with the commit
   */
  example_run_ids?: Array<string>;

  /**
   * Author's full name
   */
  full_name?: string;

  /**
   * The manifest of the commit
   */
  manifest?: unknown;

  /**
   * The SHA of the manifest
   */
  manifest_sha?: Array<number>;

  /**
   * Number of API downloads
   */
  num_downloads?: number;

  /**
   * Number of web views
   */
  num_views?: number;

  /**
   * The hash of the parent commit
   */
  parent_commit_hash?: string;

  /**
   * The ID of the parent commit
   */
  parent_id?: string;

  /**
   * Repository ID
   */
  repo_id?: string;

  /**
   * When the commit was last updated
   */
  updated_at?: string;
}

export interface CommitCreateResponse {
  commit?: CommitWithLookups;
}

export interface CommitRetrieveResponse {
  commit_hash?: string;

  description?: string;

  examples?: Array<CommitRetrieveResponse.Example>;

  is_draft?: boolean;

  manifest?: unknown;

  model_config?: unknown;

  model_provider?: string;
}

export namespace CommitRetrieveResponse {
  export interface Example {
    id?: string;

    inputs?: unknown;

    outputs?: unknown;

    session_id?: string;

    start_time?: string;
  }
}

export interface CommitCreateParams {
  /**
   * Path param: Repository owner (tenant handle) or '-' for private repos
   */
  owner: string;

  /**
   * Body param
   */
  description?: string;

  /**
   * Body param
   */
  manifest?: unknown;

  /**
   * Body param
   */
  parent_commit?: string;

  /**
   * Body param: SkipWebhooks allows skipping webhook notifications. Can be true
   * (boolean) to skip all, or an array of webhook UUIDs to skip specific ones.
   */
  skip_webhooks?: unknown;
}

export interface CommitRetrieveParams {
  /**
   * Path param: Repository owner (tenant handle) or '-' for private repos
   */
  owner: string;

  /**
   * Path param: Repository handle
   */
  repo: string;

  /**
   * Query param
   */
  get_examples?: boolean;

  /**
   * Query param: Comma-separated list of optional fields: "model", "is_draft"
   */
  include?: string;

  /**
   * Query param: Deprecated: use Include instead
   */
  include_model?: boolean;

  /**
   * Query param
   */
  is_view?: boolean;
}

export interface CommitListParams extends OffsetPaginationCommitsParams {
  /**
   * Path param: Repository owner (tenant handle) or '-' for private repos
   */
  owner: string;

  /**
   * Query param: IncludeStats determines whether to compute num_downloads and
   * num_views
   */
  include_stats?: boolean;

  /**
   * Query param: Tag filters commits to only those with a specific tag (e.g.
   * "production", "staging")
   */
  tag?: string;
}

export declare namespace Commits {
  export {
    type CommitManifestResponse as CommitManifestResponse,
    type CommitWithLookups as CommitWithLookups,
    type CommitCreateResponse as CommitCreateResponse,
    type CommitRetrieveResponse as CommitRetrieveResponse,
    type CommitWithLookupsOffsetPaginationCommits as CommitWithLookupsOffsetPaginationCommits,
    type CommitCreateParams as CommitCreateParams,
    type CommitRetrieveParams as CommitRetrieveParams,
    type CommitListParams as CommitListParams,
  };
}
