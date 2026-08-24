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
    return this._client.get(path`/api/v1/platform/issues/${id}`, options);
  }

  /**
   * **Beta:** This endpoint is in active development and may change without notice.
   *
   * Returns issues for the authenticated tenant, optionally filtered by session,
   * status, severity, tag, linked trace, or last modified time.
   */
  list(
    query: IssueListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<IssuesOffsetPaginationIssues, Issue> {
    return this._client.getAPIList('/api/v1/platform/issues', OffsetPaginationIssues<Issue>, {
      query,
      ...options,
    });
  }
}

export type IssuesOffsetPaginationIssues = OffsetPaginationIssues<Issue>;

export interface Issue {
  id?: string;

  actions?: unknown;

  auto_resolution_evidence?: unknown;

  /**
   * Nil unless eligible: "auto_close" or "prompt". Evidence carries the deciding
   * gate.
   */
  auto_resolution_state?: string;

  created_at?: string;

  description?: string;

  first_seen_at?: string;

  fix_branch?: string;

  fix_dispatched_at?: string;

  fix_pr_number?: number;

  fix_prompt?: string;

  fix_verification?: unknown;

  last_seen_at?: string;

  linear_sync?: Issue.LinearSync;

  name?: string;

  proposed_context_fixes?: Array<unknown>;

  proposed_examples?: Array<unknown>;

  proposed_fix?: string;

  proposed_prompt_fixes?: Array<unknown>;

  /**
   * RecurrencesSinceWatching counts linked traces whose run start_time is after
   * watching_since — i.e. recurrences observed during the current watch period.
   */
  recurrences_since_watching?: number;

  session_id?: string;

  severity?: 0 | 1 | 2 | 3;

  status?: 'open' | 'fixing' | 'watching' | 'completed' | 'ignored';

  tags?: Array<string>;

  tenant_id?: string;

  traces?: unknown;

  updated_at?: string;

  watching_since?: string;
}

export namespace Issue {
  export interface LinearSync {
    identifier?: string;

    issue_id?: string;

    last_attempted_at?: string;

    last_error?: string;

    last_synced_at?: string;

    linear_issue_id?: string;

    state?: 'pending' | 'synced' | 'failed' | 'auth_required' | 'paused';

    url?: string;
  }
}

export interface IssueListParams extends OffsetPaginationIssuesParams {
  /**
   * Filter by Engine activity (repeatable; OR semantics)
   */
  activity?: Array<'fixing' | 'watching' | 'recurred'>;

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
   * Filter by exact severity (repeatable; OR semantics)
   */
  severity_exact?: Array<0 | 1 | 2 | 3>;

  /**
   * Sort field
   */
  sort_by?:
    'default' | 'created_at' | 'updated_at' | 'last_seen' | 'last_updated' | 'trace_count' | 'severity';

  /**
   * Filter by status
   */
  status?: 'open' | 'fixing' | 'watching' | 'completed' | 'ignored';

  /**
   * Group results by issue lifecycle status before applying sort_by
   */
  status_first?: boolean;

  /**
   * Filter by tag (exact match)
   */
  tag?: string;

  /**
   * Return only issues with a linked run in this trace
   */
  trace_id?: string;

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
