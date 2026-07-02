// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { OffsetPaginationIssues, type OffsetPaginationIssuesParams, PagePromise } from '../core/pagination.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class Issues extends APIResource {
  /**
   * **Beta:** This endpoint is in active development and may change without notice.
   *
   * Returns one issue for the authenticated tenant.
   */
  retrieve(id: string, options?: RequestOptions): APIPromise<Issue> {
    return this._client.get(path`/v1/platform/issues/${id}`, options);
  }

  /**
   * **Beta:** This endpoint is in active development and may change without notice.
   *
   * Returns issues for the authenticated tenant, optionally filtered by session,
   * status, severity, tag, or last modified time.
   */
  list(
    query: IssueListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<IssuesOffsetPaginationIssues, Issue> {
    return this._client.getAPIList('/v1/platform/issues', OffsetPaginationIssues<Issue>, {
      query,
      ...options,
    });
  }
}

export type IssuesOffsetPaginationIssues = OffsetPaginationIssues<Issue>;

export interface Issue {
  id?: string;

  actions?: unknown;

  created_at?: string;

  description?: string;

  first_seen_at?: string;

  fix_branch?: string;

  fix_dispatched_at?: string;

  fix_pr_number?: number;

  fix_prompt?: string;

  fix_verification?: unknown;

  last_seen_at?: string;

  name?: string;

  proposed_context_fixes?: Array<unknown>;

  proposed_examples?: Array<unknown>;

  proposed_fix?: string;

  proposed_prompt_fixes?: Array<unknown>;

  session_id?: string;

  severity?: 0 | 1 | 2 | 3;

  status?: 'open' | 'completed' | 'ignored';

  tags?: Array<string>;

  tenant_id?: string;

  traces?: unknown;

  updated_at?: string;
}

export interface IssueListParams extends OffsetPaginationIssuesParams {
  /**
   * Filter by session ID (UUID)
   */
  session_id?: string;

  /**
   * Filter by session name (exact match)
   */
  session_name?: string;

  /**
   * Filter by severity
   */
  severity?: 0 | 1 | 2 | 3;

  /**
   * Sort field
   */
  sort_by?: 'created_at' | 'updated_at' | 'severity';

  /**
   * Filter by status
   */
  status?: 'open' | 'completed' | 'ignored';

  /**
   * Filter by tag (exact match)
   */
  tag?: string;

  /**
   * Return only issues updated at or after this RFC3339 timestamp
   */
  updated_at?: string;
}

export declare namespace Issues {
  export {
    type Issue as Issue,
    type IssuesOffsetPaginationIssues as IssuesOffsetPaginationIssues,
    type IssueListParams as IssueListParams,
  };
}
