// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RunsAPI from '../runs.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Runs extends APIResource {
  /**
   * Fetch examples for a dataset, and fetch the runs for each example if they are
   * associated with the given session_ids.
   */
  query(
    datasetID: string,
    params: RunQueryParams,
    options?: RequestOptions,
  ): APIPromise<RunQueryResponse | null> {
    const { format, ...body } = params;
    return this._client.post(path`/api/v1/datasets/${datasetID}/runs`, {
      query: { format },
      body,
      ...options,
    });
  }
}

/**
 * Example schema with list of runs from ClickHouse.
 *
 * For non-grouped endpoint (/datasets/{dataset_id}/runs): runs from single
 * session. For grouped endpoint (/datasets/{dataset_id}/group/runs): flat array of
 * runs from all sessions, where each run has a session_id field for frontend to
 * determine column placement.
 */
export interface ExampleWithRunsCh {
  id: string;

  dataset_id: string;

  inputs: { [key: string]: unknown };

  name: string;

  runs: Array<ExampleWithRunsCh.Run>;

  attachment_urls?: { [key: string]: unknown } | null;

  created_at?: string;

  metadata?: { [key: string]: unknown } | null;

  modified_at?: string | null;

  outputs?: { [key: string]: unknown } | null;

  source_run_id?: string | null;

  source_run_start_time?: string | null;

  source_session_id?: string | null;

  source_trace_id?: string | null;
}

export namespace ExampleWithRunsCh {
  /**
   * Run schema for comparison view.
   */
  export interface Run {
    id: string;

    name: string;

    /**
     * Enum for run types.
     */
    run_type: RunsAPI.RunTypeEnum;

    session_id: string;

    status: string;

    trace_id: string;

    app_path?: string | null;

    completion_cost?: string | null;

    completion_tokens?: number | null;

    dotted_order?: string | null;

    end_time?: string | null;

    error?: string | null;

    events?: Array<{ [key: string]: unknown }> | null;

    execution_order?: number;

    extra?: { [key: string]: unknown } | null;

    feedback_stats?: { [key: string]: { [key: string]: unknown } } | null;

    first_token_time?: string | null;

    inputs?: { [key: string]: unknown } | null;

    inputs_preview?: string | null;

    inputs_s3_urls?: { [key: string]: unknown } | null;

    manifest_id?: string | null;

    manifest_s3_id?: string | null;

    outputs?: { [key: string]: unknown } | null;

    outputs_preview?: string | null;

    outputs_s3_urls?: { [key: string]: unknown } | null;

    parent_run_id?: string | null;

    prompt_cost?: string | null;

    prompt_tokens?: number | null;

    reference_example_id?: string | null;

    s3_urls?: { [key: string]: unknown } | null;

    serialized?: { [key: string]: unknown } | null;

    start_time?: string;

    tags?: Array<string> | null;

    total_cost?: string | null;

    total_tokens?: number | null;

    trace_max_start_time?: string | null;

    trace_min_start_time?: string | null;
  }
}

export interface QueryExampleSchemaWithRuns {
  session_ids: Array<string>;

  comparative_experiment_id?: string | null;

  example_ids?: Array<string> | null;

  filters?: { [key: string]: Array<string> } | null;

  include_annotator_detail?: boolean;

  limit?: number;

  offset?: number;

  preview?: boolean;

  sort_params?: SortParamsForRunsComparisonView | null;
}

export interface SortParamsForRunsComparisonView {
  sort_by: string;

  sort_order?: 'ASC' | 'DESC';
}

export type RunQueryResponse = Array<ExampleWithRunsCh>;

export interface RunQueryParams {
  /**
   * Body param
   */
  session_ids: Array<string>;

  /**
   * Query param: Response format, e.g., 'csv'
   */
  format?: 'csv' | null;

  /**
   * Body param
   */
  comparative_experiment_id?: string | null;

  /**
   * Body param
   */
  example_ids?: Array<string> | null;

  /**
   * Body param
   */
  filters?: { [key: string]: Array<string> } | null;

  /**
   * Body param
   */
  include_annotator_detail?: boolean;

  /**
   * Body param
   */
  limit?: number | null;

  /**
   * Body param
   */
  offset?: number;

  /**
   * Body param
   */
  preview?: boolean;

  /**
   * Body param
   */
  sort_params?: SortParamsForRunsComparisonView | null;
}

export declare namespace Runs {
  export {
    type ExampleWithRunsCh as ExampleWithRunsCh,
    type QueryExampleSchemaWithRuns as QueryExampleSchemaWithRuns,
    type SortParamsForRunsComparisonView as SortParamsForRunsComparisonView,
    type RunQueryResponse as RunQueryResponse,
    type RunQueryParams as RunQueryParams,
  };
}
