// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  OffsetPaginationInsightsClusteringJobs,
  type OffsetPaginationInsightsClusteringJobsParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Insights extends APIResource {
  /**
   * Create an insights job.
   */
  create(
    sessionID: string,
    body: InsightCreateParams,
    options?: RequestOptions,
  ): APIPromise<InsightCreateResponse> {
    return this._client.post(path`/api/v1/sessions/${sessionID}/insights`, { body, ...options });
  }

  /**
   * Update a session cluster job.
   */
  update(
    jobID: string,
    params: InsightUpdateParams,
    options?: RequestOptions,
  ): APIPromise<InsightUpdateResponse> {
    const { session_id, ...body } = params;
    return this._client.patch(path`/api/v1/sessions/${session_id}/insights/${jobID}`, { body, ...options });
  }

  /**
   * Get all clusters for a session.
   */
  list(
    sessionID: string,
    query: InsightListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<InsightListResponsesOffsetPaginationInsightsClusteringJobs, InsightListResponse> {
    return this._client.getAPIList(
      path`/api/v1/sessions/${sessionID}/insights`,
      OffsetPaginationInsightsClusteringJobs<InsightListResponse>,
      { query, ...options },
    );
  }

  /**
   * Delete a session cluster job.
   */
  delete(
    jobID: string,
    params: InsightDeleteParams,
    options?: RequestOptions,
  ): APIPromise<InsightDeleteResponse> {
    const { session_id } = params;
    return this._client.delete(path`/api/v1/sessions/${session_id}/insights/${jobID}`, options);
  }

  /**
   * Get a specific cluster job for a session.
   */
  retrieveJob(
    jobID: string,
    params: InsightRetrieveJobParams,
    options?: RequestOptions,
  ): APIPromise<InsightRetrieveJobResponse> {
    const { session_id } = params;
    return this._client.get(path`/api/v1/sessions/${session_id}/insights/${jobID}`, options);
  }

  /**
   * Get all runs for a cluster job, optionally filtered by cluster.
   */
  retrieveRuns(
    jobID: string,
    params: InsightRetrieveRunsParams,
    options?: RequestOptions,
  ): APIPromise<InsightRetrieveRunsResponse> {
    const { session_id, ...query } = params;
    return this._client.get(path`/api/v1/sessions/${session_id}/insights/${jobID}/runs`, {
      query,
      ...options,
    });
  }
}

export type InsightListResponsesOffsetPaginationInsightsClusteringJobs =
  OffsetPaginationInsightsClusteringJobs<InsightListResponse>;

/**
 * Request to create a run clustering job.
 */
export interface CreateRunClusteringJobRequest {
  attribute_schemas?: { [key: string]: unknown } | null;

  cluster_model?: string | null;

  config_id?: string | null;

  end_time?: string | null;

  filter?: string | null;

  hierarchy?: Array<number> | null;

  is_scheduled?: boolean;

  last_n_hours?: number | null;

  model?: 'openai' | 'anthropic';

  name?: string | null;

  partitions?: { [key: string]: string } | null;

  sample?: number | null;

  start_time?: string | null;

  summary_model?: string | null;

  summary_prompt?: string | null;

  user_context?: { [key: string]: string } | null;

  validate_model_secrets?: boolean;
}

/**
 * Response to creating a run clustering job.
 */
export interface InsightCreateResponse {
  id: string;

  name: string;

  status: string;

  error?: string | null;
}

/**
 * Response to update a session cluster job.
 */
export interface InsightUpdateResponse {
  name: string;

  status: string;
}

/**
 * Session cluster job
 */
export interface InsightListResponse {
  id: string;

  created_at: string;

  name: string;

  status: string;

  config_id?: string | null;

  end_time?: string | null;

  error?: string | null;

  metadata?: { [key: string]: unknown } | null;

  shape?: { [key: string]: number } | null;

  start_time?: string | null;
}

/**
 * Response to delete a session cluster job.
 */
export interface InsightDeleteResponse {
  id: string;

  message: string;
}

/**
 * Response to get a specific cluster job for a session.
 */
export interface InsightRetrieveJobResponse {
  id: string;

  clusters: Array<InsightRetrieveJobResponse.Cluster>;

  created_at: string;

  name: string;

  status: string;

  config_id?: string | null;

  end_time?: string | null;

  error?: string | null;

  metadata?: { [key: string]: unknown } | null;

  /**
   * High level summary of an insights job that pulls out patterns and specific
   * traces.
   */
  report?: InsightRetrieveJobResponse.Report | null;

  shape?: { [key: string]: number } | null;

  start_time?: string | null;
}

export namespace InsightRetrieveJobResponse {
  /**
   * A single cluster of runs.
   */
  export interface Cluster {
    id: string;

    description: string;

    level: number;

    name: string;

    num_runs: number;

    stats: { [key: string]: unknown } | null;

    parent_id?: string | null;

    parent_name?: string | null;
  }

  /**
   * High level summary of an insights job that pulls out patterns and specific
   * traces.
   */
  export interface Report {
    created_at?: string | null;

    highlighted_traces?: Array<Report.HighlightedTrace>;

    key_points?: Array<string>;

    title?: string | null;
  }

  export namespace Report {
    /**
     * A trace highlighted in an insights report summary. Up to 10 per insights job.
     */
    export interface HighlightedTrace {
      highlight_reason: string;

      rank: number;

      run_id: string;

      cluster_id?: string | null;

      cluster_name?: string | null;

      summary?: string | null;
    }
  }
}

export interface InsightRetrieveRunsResponse {
  offset: number | null;

  runs: Array<{ [key: string]: unknown }>;
}

export interface InsightCreateParams {
  attribute_schemas?: { [key: string]: unknown } | null;

  cluster_model?: string | null;

  config_id?: string | null;

  end_time?: string | null;

  filter?: string | null;

  hierarchy?: Array<number> | null;

  is_scheduled?: boolean;

  last_n_hours?: number | null;

  model?: 'openai' | 'anthropic';

  name?: string | null;

  partitions?: { [key: string]: string } | null;

  sample?: number | null;

  start_time?: string | null;

  summary_model?: string | null;

  summary_prompt?: string | null;

  user_context?: { [key: string]: string } | null;

  validate_model_secrets?: boolean;
}

export interface InsightUpdateParams {
  /**
   * Path param
   */
  session_id: string;

  /**
   * Body param
   */
  name: string;
}

export interface InsightListParams extends OffsetPaginationInsightsClusteringJobsParams {
  config_id?: string | null;

  legacy?: boolean | null;
}

export interface InsightDeleteParams {
  session_id: string;
}

export interface InsightRetrieveJobParams {
  session_id: string;
}

export interface InsightRetrieveRunsParams {
  /**
   * Path param
   */
  session_id: string;

  /**
   * Query param
   */
  attribute_sort_key?: string | null;

  /**
   * Query param
   */
  attribute_sort_order?: 'asc' | 'desc' | null;

  /**
   * Query param
   */
  cluster_id?: string | null;

  /**
   * Query param
   */
  limit?: number;

  /**
   * Query param
   */
  offset?: number;
}

export declare namespace Insights {
  export {
    type CreateRunClusteringJobRequest as CreateRunClusteringJobRequest,
    type InsightCreateResponse as InsightCreateResponse,
    type InsightUpdateResponse as InsightUpdateResponse,
    type InsightListResponse as InsightListResponse,
    type InsightDeleteResponse as InsightDeleteResponse,
    type InsightRetrieveJobResponse as InsightRetrieveJobResponse,
    type InsightRetrieveRunsResponse as InsightRetrieveRunsResponse,
    type InsightListResponsesOffsetPaginationInsightsClusteringJobs as InsightListResponsesOffsetPaginationInsightsClusteringJobs,
    type InsightCreateParams as InsightCreateParams,
    type InsightUpdateParams as InsightUpdateParams,
    type InsightListParams as InsightListParams,
    type InsightDeleteParams as InsightDeleteParams,
    type InsightRetrieveJobParams as InsightRetrieveJobParams,
    type InsightRetrieveRunsParams as InsightRetrieveRunsParams,
  };
}
