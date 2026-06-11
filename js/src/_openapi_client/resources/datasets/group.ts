// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as RunsAPI from './runs';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Group extends APIResource {
  /**
   * Fetch examples for a dataset, and fetch the runs for each example if they are
   * associated with the given session_ids.
   */
  runs(datasetID: string, body: GroupRunsParams, options?: RequestOptions): APIPromise<GroupRunsResponse> {
    return this._client.post(path`/api/v1/datasets/${datasetID}/group/runs`, { body, ...options });
  }
}

/**
 * Response for grouped comparison view of dataset examples.
 *
 * Returns dataset examples grouped by a run metadata value (e.g., model='gpt-4').
 * Optional filters are applied to all runs before grouping.
 *
 * Shows:
 *
 * - Which examples were executed with each metadata value
 * - Per-session aggregate statistics for runs on those examples
 * - The actual example data with their associated runs
 *
 * Used for comparing how different sessions performed on the same set of examples.
 */
export interface GroupRunsResponse {
  groups: Array<GroupRunsResponse.Group>;
}

export namespace GroupRunsResponse {
  /**
   * Group of examples with a specific metadata value across multiple sessions.
   *
   * Extends RunGroupBase with:
   *
   * - group_key: metadata value that defines this group
   * - sessions: per-session stats for runs matching this metadata value
   * - examples: shared examples across all sessions (intersection logic) with flat
   *   array of runs (each run has session_id field for frontend to determine column)
   * - example_count: unique example count (pagination-aware, same across all
   *   sessions due to intersection)
   *
   * Inherited from RunGroupBase:
   *
   * - filter: metadata filter for this group (e.g., "and(eq(is_root, true),
   *   and(eq(metadata_key, 'model'), eq(metadata_value, 'gpt-4')))")
   * - count: total run count across all sessions (includes duplicate runs)
   * - total_tokens, total_cost: aggregate across sessions
   * - min_start_time, max_start_time: time range across sessions
   * - latency_p50, latency_p99: aggregate latency stats across sessions
   * - feedback_stats: weighted average feedback across sessions
   *
   * Additional aggregate stats:
   *
   * - prompt_tokens, completion_tokens: separate token counts
   * - prompt_cost, completion_cost: separate costs
   * - error_rate: average error rate
   */
  export interface Group {
    example_count: number;

    examples: Array<RunsAPI.ExampleWithRunsCh>;

    filter: string;

    group_key: string | number;

    sessions: Array<Group.Session>;

    completion_cost?: string | null;

    completion_tokens?: number | null;

    count?: number | null;

    error_rate?: number | null;

    feedback_stats?: { [key: string]: unknown } | null;

    latency_p50?: number | null;

    latency_p99?: number | null;

    max_start_time?: string | null;

    min_start_time?: string | null;

    prompt_cost?: string | null;

    prompt_tokens?: number | null;

    total_cost?: string | null;

    total_tokens?: number | null;
  }

  export namespace Group {
    /**
     * TracerSession stats filtered to runs matching a specific metadata value.
     *
     * Extends TracerSession with:
     *
     * - example_count: unique examples (vs run_count = total runs including
     *   duplicates)
     * - filter: ClickHouse filter for fetching runs in this session/group
     * - min/max_start_time: time range for runs in this session/group
     */
    export interface Session {
      id: string;

      filter: string;

      tenant_id: string;

      completion_cost?: string | null;

      completion_tokens?: number | null;

      default_dataset_id?: string | null;

      description?: string | null;

      end_time?: string | null;

      error_rate?: number | null;

      example_count?: number | null;

      experiment_progress?: Session.ExperimentProgress | null;

      extra?: { [key: string]: unknown } | null;

      feedback_stats?: { [key: string]: unknown } | null;

      first_token_p50?: number | null;

      first_token_p99?: number | null;

      last_run_start_time?: string | null;

      last_run_start_time_live?: string | null;

      latency_p50?: number | null;

      latency_p99?: number | null;

      max_start_time?: string | null;

      min_start_time?: string | null;

      name?: string;

      prompt_cost?: string | null;

      prompt_tokens?: number | null;

      reference_dataset_id?: string | null;

      run_count?: number | null;

      run_facets?: Array<{ [key: string]: unknown }> | null;

      session_feedback_stats?: { [key: string]: unknown } | null;

      start_time?: string;

      streaming_rate?: number | null;

      test_run_number?: number | null;

      total_cost?: string | null;

      total_tokens?: number | null;

      trace_tier?: 'longlived' | 'shortlived' | null;
    }

    export namespace Session {
      export interface ExperimentProgress {
        evaluator_progress: { [key: string]: number };

        expected_run_count: number;

        run_progress: number;
      }
    }
  }
}

export interface GroupRunsParams {
  group_by: 'run_metadata' | 'example_metadata';

  metadata_key: string;

  session_ids: Array<string>;

  filters?: { [key: string]: Array<string> } | null;

  limit?: number;

  offset?: number;

  per_group_limit?: number;

  preview?: boolean;
}

export declare namespace Group {
  export { type GroupRunsResponse as GroupRunsResponse, type GroupRunsParams as GroupRunsParams };
}
