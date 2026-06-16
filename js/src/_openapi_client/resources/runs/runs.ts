// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RulesAPI from './rules.js';
import { Rules } from './rules.js';
import * as SessionsAPI from '../sessions/sessions.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Runs extends APIResource {
  rules: RulesAPI.Rules = new RulesAPI.Rules(this._client);

  /**
   * Queues a single run for ingestion. The request body must be a JSON-encoded run
   * object that follows the Run schema.
   */
  create(body: RunCreateParams, options?: RequestOptions): APIPromise<RunCreateResponse> {
    return this._client.post('/runs', { body, ...options });
  }

  /**
   * Get a specific run.
   */
  retrieve(
    runID: string,
    query: RunRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<RunSchema> {
    return this._client.get(path`/api/v1/runs/${runID}`, { query, ...options });
  }

  /**
   * Updates a run identified by its ID. The body should contain only the fields to
   * be changed; unknown fields are ignored.
   */
  update(runID: string, body: RunUpdateParams, options?: RequestOptions): APIPromise<RunUpdateResponse> {
    return this._client.patch(path`/runs/${runID}`, { body, ...options });
  }

  /**
   * Ingests a batch of runs in a single JSON payload. The payload must have `post`
   * and/or `patch` arrays containing run objects. Prefer this endpoint over
   * single‑run ingestion when submitting hundreds of runs, but `/runs/multipart`
   * offers better handling for very large fields and attachments.
   */
  ingestBatch(body: RunIngestBatchParams, options?: RequestOptions): APIPromise<RunIngestBatchResponse> {
    return this._client.post('/runs/batch', { body, ...options });
  }

  /**
   * Query Runs
   */
  query(body: RunQueryParams, options?: RequestOptions): APIPromise<RunQueryResponse> {
    return this._client.post('/api/v1/runs/query', { body, ...options });
  }

  /**
   * Get all runs by query in body payload.
   */
  stats(body: RunStatsParams, options?: RequestOptions): APIPromise<RunStatsResponse> {
    return this._client.post('/api/v1/runs/stats', { body, ...options });
  }

  /**
   * Update a run.
   */
  update2(runID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.patch(path`/api/v1/runs/${runID}`, options);
  }
}

/**
 * Query params for run endpoints.
 */
export interface BodyParamsForRunSchema {
  id?: Array<string> | null;

  cursor?: string | null;

  /**
   * Enum for run data source types.
   */
  data_source_type?: RunsFilterDataSourceTypeEnum | null;

  end_time?: string | null;

  error?: boolean | null;

  execution_order?: number | null;

  filter?: string | null;

  is_root?: boolean | null;

  limit?: number;

  /**
   * Enum for run start date order.
   */
  order?: 'asc' | 'desc';

  parent_run?: string | null;

  query?: string | null;

  reference_example?: Array<string> | null;

  /**
   * Enum for run types.
   */
  run_type?: RunTypeEnum | null;

  search_filter?: string | null;

  select?: Array<
    | 'id'
    | 'name'
    | 'run_type'
    | 'start_time'
    | 'end_time'
    | 'status'
    | 'error'
    | 'extra'
    | 'events'
    | 'inputs'
    | 'inputs_preview'
    | 'inputs_s3_urls'
    | 'inputs_or_signed_url'
    | 'outputs'
    | 'outputs_preview'
    | 'outputs_s3_urls'
    | 'outputs_or_signed_url'
    | 's3_urls'
    | 'error_or_signed_url'
    | 'events_or_signed_url'
    | 'extra_or_signed_url'
    | 'serialized_or_signed_url'
    | 'parent_run_id'
    | 'manifest_id'
    | 'manifest_s3_id'
    | 'manifest'
    | 'session_id'
    | 'serialized'
    | 'reference_example_id'
    | 'reference_dataset_id'
    | 'total_tokens'
    | 'prompt_tokens'
    | 'prompt_token_details'
    | 'completion_tokens'
    | 'completion_token_details'
    | 'total_cost'
    | 'prompt_cost'
    | 'prompt_cost_details'
    | 'completion_cost'
    | 'completion_cost_details'
    | 'price_model_id'
    | 'first_token_time'
    | 'trace_id'
    | 'dotted_order'
    | 'last_queued_at'
    | 'feedback_stats'
    | 'child_run_ids'
    | 'parent_run_ids'
    | 'tags'
    | 'in_dataset'
    | 'app_path'
    | 'share_token'
    | 'trace_tier'
    | 'trace_first_received_at'
    | 'ttl_seconds'
    | 'trace_upgrade'
    | 'thread_id'
    | 'trace_min_max_start_time'
    | 'messages'
    | 'inserted_at'
  >;

  session?: Array<string> | null;

  skip_pagination?: boolean | null;

  skip_prev_cursor?: boolean;

  start_time?: string | null;

  trace?: string | null;

  trace_filter?: string | null;

  tree_filter?: string | null;

  use_experimental_search?: boolean;
}

export interface RequestBodyForRunsGenerateQuery {
  query: string;

  feedback_keys?: Array<
    | 'user_score'
    | 'user_edited'
    | 'user_removed'
    | 'user_opened_run'
    | 'user_selected_run'
    | 'results_size'
    | 'valid_filter'
  >;
}

export interface ResponseBodyForRunsGenerateQuery {
  feedback_urls: { [key: string]: string };

  filter: string;
}

export interface Run {
  id?: string;

  dotted_order?: string;

  end_time?: string;

  error?: string;

  events?: Array<{ [key: string]: unknown }>;

  extra?: { [key: string]: unknown };

  input_attachments?: { [key: string]: unknown };

  inputs?: { [key: string]: unknown };

  name?: string;

  output_attachments?: { [key: string]: unknown };

  outputs?: { [key: string]: unknown };

  parent_run_id?: string;

  reference_example_id?: string;

  run_type?: 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

  serialized?: { [key: string]: unknown };

  session_id?: string;

  session_name?: string;

  start_time?: string;

  status?: string;

  tags?: Array<string>;

  trace_id?: string;
}

/**
 * Run schema.
 */
export interface RunSchema {
  id: string;

  app_path: string;

  dotted_order: string;

  name: string;

  /**
   * Enum for run types.
   */
  run_type: RunTypeEnum;

  session_id: string;

  status: string;

  trace_id: string;

  child_run_ids?: Array<string> | null;

  completion_cost?: string | null;

  completion_cost_details?: { [key: string]: string } | null;

  completion_token_details?: { [key: string]: number } | null;

  completion_tokens?: number;

  direct_child_run_ids?: Array<string> | null;

  end_time?: string | null;

  error?: string | null;

  events?: Array<{ [key: string]: unknown }> | null;

  execution_order?: number;

  extra?: { [key: string]: unknown } | null;

  feedback_stats?: { [key: string]: { [key: string]: unknown } } | null;

  first_token_time?: string | null;

  in_dataset?: boolean | null;

  inputs?: { [key: string]: unknown } | null;

  inputs_preview?: string | null;

  inputs_s3_urls?: { [key: string]: unknown } | null;

  last_queued_at?: string | null;

  manifest_id?: string | null;

  manifest_s3_id?: string | null;

  messages?: Array<{ [key: string]: unknown }> | null;

  outputs?: { [key: string]: unknown } | null;

  outputs_preview?: string | null;

  outputs_s3_urls?: { [key: string]: unknown } | null;

  parent_run_id?: string | null;

  parent_run_ids?: Array<string> | null;

  price_model_id?: string | null;

  prompt_cost?: string | null;

  prompt_cost_details?: { [key: string]: string } | null;

  prompt_token_details?: { [key: string]: number } | null;

  prompt_tokens?: number;

  reference_dataset_id?: string | null;

  reference_example_id?: string | null;

  s3_urls?: { [key: string]: unknown } | null;

  serialized?: { [key: string]: unknown } | null;

  share_token?: string | null;

  start_time?: string;

  tags?: Array<string> | null;

  thread_id?: string | null;

  total_cost?: string | null;

  total_tokens?: number;

  trace_first_received_at?: string | null;

  trace_max_start_time?: string | null;

  trace_min_start_time?: string | null;

  trace_tier?: 'longlived' | 'shortlived' | null;

  trace_upgrade?: boolean;

  ttl_seconds?: number | null;
}

/**
 * Query params for run stats.
 */
export interface RunStatsQueryParams {
  id?: Array<string> | null;

  /**
   * Enum for run data source types.
   */
  data_source_type?: RunsFilterDataSourceTypeEnum | null;

  end_time?: string | null;

  error?: boolean | null;

  execution_order?: number | null;

  filter?: string | null;

  /**
   * Group by param for run stats.
   */
  group_by?: SessionsAPI.RunStatsGroupBy | null;

  groups?: Array<string | null> | null;

  is_root?: boolean | null;

  parent_run?: string | null;

  query?: string | null;

  reference_example?: Array<string> | null;

  /**
   * Enum for run types.
   */
  run_type?: RunTypeEnum | null;

  search_filter?: string | null;

  select?: Array<
    | 'run_count'
    | 'latency_p50'
    | 'latency_p99'
    | 'latency_avg'
    | 'first_token_p50'
    | 'first_token_p99'
    | 'total_tokens'
    | 'prompt_tokens'
    | 'completion_tokens'
    | 'median_tokens'
    | 'completion_tokens_p50'
    | 'prompt_tokens_p50'
    | 'tokens_p99'
    | 'completion_tokens_p99'
    | 'prompt_tokens_p99'
    | 'last_run_start_time'
    | 'feedback_stats'
    | 'thread_feedback_stats'
    | 'run_facets'
    | 'error_rate'
    | 'streaming_rate'
    | 'total_cost'
    | 'prompt_cost'
    | 'completion_cost'
    | 'cost_p50'
    | 'cost_p99'
    | 'session_feedback_stats'
    | 'all_run_stats'
    | 'all_token_stats'
    | 'group_count'
    | 'prompt_token_details'
    | 'completion_token_details'
    | 'prompt_cost_details'
    | 'completion_cost_details'
  > | null;

  session?: Array<string> | null;

  skip_pagination?: boolean | null;

  start_time?: string | null;

  trace?: string | null;

  trace_filter?: string | null;

  tree_filter?: string | null;

  use_experimental_search?: boolean;
}

/**
 * Enum for run types.
 */
export type RunTypeEnum = 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

/**
 * Enum for run data source types.
 */
export type RunsFilterDataSourceTypeEnum =
  | 'current'
  | 'historical'
  | 'lite'
  | 'root_lite'
  | 'runs_feedbacks_rmt_wide';

export type RunCreateResponse = { [key: string]: RunCreateResponse.item };

export namespace RunCreateResponse {
  export interface item {}
}

export type RunUpdateResponse = { [key: string]: RunUpdateResponse.item };

export namespace RunUpdateResponse {
  export interface item {}
}

export type RunIngestBatchResponse = { [key: string]: RunIngestBatchResponse.item };

export namespace RunIngestBatchResponse {
  export interface item {}
}

export interface RunQueryResponse {
  cursors: { [key: string]: string | null };

  runs: Array<RunSchema>;

  parsed_query?: string | null;

  search_cursors?: { [key: string]: unknown } | null;
}

export type RunStatsResponse = RunStatsResponse.RunStats | { [key: string]: RunStatsResponse.RunStats };

export namespace RunStatsResponse {
  export interface RunStats {
    completion_cost?: number | null;

    completion_cost_details?: { [key: string]: unknown } | null;

    completion_token_details?: { [key: string]: unknown } | null;

    completion_tokens?: number | null;

    completion_tokens_p50?: number | null;

    completion_tokens_p99?: number | null;

    cost_p50?: number | null;

    cost_p99?: number | null;

    error_rate?: number | null;

    feedback_stats?: { [key: string]: unknown } | null;

    first_token_p50?: number | null;

    first_token_p99?: number | null;

    last_run_start_time?: string | null;

    latency_p50?: number | null;

    latency_p99?: number | null;

    median_tokens?: number | null;

    prompt_cost?: number | null;

    prompt_cost_details?: { [key: string]: unknown } | null;

    prompt_token_details?: { [key: string]: unknown } | null;

    prompt_tokens?: number | null;

    prompt_tokens_p50?: number | null;

    prompt_tokens_p99?: number | null;

    run_count?: number | null;

    run_facets?: Array<{ [key: string]: unknown }> | null;

    streaming_rate?: number | null;

    tokens_p99?: number | null;

    total_cost?: number | null;

    total_tokens?: number | null;
  }

  export interface RunStats {
    completion_cost?: number | null;

    completion_cost_details?: { [key: string]: unknown } | null;

    completion_token_details?: { [key: string]: unknown } | null;

    completion_tokens?: number | null;

    completion_tokens_p50?: number | null;

    completion_tokens_p99?: number | null;

    cost_p50?: number | null;

    cost_p99?: number | null;

    error_rate?: number | null;

    feedback_stats?: { [key: string]: unknown } | null;

    first_token_p50?: number | null;

    first_token_p99?: number | null;

    last_run_start_time?: string | null;

    latency_p50?: number | null;

    latency_p99?: number | null;

    median_tokens?: number | null;

    prompt_cost?: number | null;

    prompt_cost_details?: { [key: string]: unknown } | null;

    prompt_token_details?: { [key: string]: unknown } | null;

    prompt_tokens?: number | null;

    prompt_tokens_p50?: number | null;

    prompt_tokens_p99?: number | null;

    run_count?: number | null;

    run_facets?: Array<{ [key: string]: unknown }> | null;

    streaming_rate?: number | null;

    tokens_p99?: number | null;

    total_cost?: number | null;

    total_tokens?: number | null;
  }
}

export type RunUpdate2Response = unknown;

export interface RunCreateParams {
  id?: string;

  dotted_order?: string;

  end_time?: string;

  error?: string;

  events?: Array<{ [key: string]: unknown }>;

  extra?: { [key: string]: unknown };

  input_attachments?: { [key: string]: unknown };

  inputs?: { [key: string]: unknown };

  name?: string;

  output_attachments?: { [key: string]: unknown };

  outputs?: { [key: string]: unknown };

  parent_run_id?: string;

  reference_example_id?: string;

  run_type?: 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

  serialized?: { [key: string]: unknown };

  session_id?: string;

  session_name?: string;

  start_time?: string;

  status?: string;

  tags?: Array<string>;

  trace_id?: string;
}

export interface RunRetrieveParams {
  exclude_s3_stored_attributes?: boolean;

  exclude_serialized?: boolean;

  include_messages?: boolean;

  session_id?: string | null;

  start_time?: string | null;
}

export interface RunUpdateParams {
  id?: string;

  dotted_order?: string;

  end_time?: string;

  error?: string;

  events?: Array<{ [key: string]: unknown }>;

  extra?: { [key: string]: unknown };

  input_attachments?: { [key: string]: unknown };

  inputs?: { [key: string]: unknown };

  name?: string;

  output_attachments?: { [key: string]: unknown };

  outputs?: { [key: string]: unknown };

  parent_run_id?: string;

  reference_example_id?: string;

  run_type?: 'tool' | 'chain' | 'llm' | 'retriever' | 'embedding' | 'prompt' | 'parser';

  serialized?: { [key: string]: unknown };

  session_id?: string;

  session_name?: string;

  start_time?: string;

  status?: string;

  tags?: Array<string>;

  trace_id?: string;
}

export interface RunIngestBatchParams {
  patch?: Array<Run>;

  post?: Array<Run>;
}

export interface RunQueryParams {
  id?: Array<string> | null;

  cursor?: string | null;

  /**
   * Enum for run data source types.
   */
  data_source_type?: RunsFilterDataSourceTypeEnum | null;

  end_time?: string | null;

  error?: boolean | null;

  execution_order?: number | null;

  filter?: string | null;

  is_root?: boolean | null;

  limit?: number;

  /**
   * Enum for run start date order.
   */
  order?: 'asc' | 'desc';

  parent_run?: string | null;

  query?: string | null;

  reference_example?: Array<string> | null;

  /**
   * Enum for run types.
   */
  run_type?: RunTypeEnum | null;

  search_filter?: string | null;

  select?: Array<
    | 'id'
    | 'name'
    | 'run_type'
    | 'start_time'
    | 'end_time'
    | 'status'
    | 'error'
    | 'extra'
    | 'events'
    | 'inputs'
    | 'inputs_preview'
    | 'inputs_s3_urls'
    | 'inputs_or_signed_url'
    | 'outputs'
    | 'outputs_preview'
    | 'outputs_s3_urls'
    | 'outputs_or_signed_url'
    | 's3_urls'
    | 'error_or_signed_url'
    | 'events_or_signed_url'
    | 'extra_or_signed_url'
    | 'serialized_or_signed_url'
    | 'parent_run_id'
    | 'manifest_id'
    | 'manifest_s3_id'
    | 'manifest'
    | 'session_id'
    | 'serialized'
    | 'reference_example_id'
    | 'reference_dataset_id'
    | 'total_tokens'
    | 'prompt_tokens'
    | 'prompt_token_details'
    | 'completion_tokens'
    | 'completion_token_details'
    | 'total_cost'
    | 'prompt_cost'
    | 'prompt_cost_details'
    | 'completion_cost'
    | 'completion_cost_details'
    | 'price_model_id'
    | 'first_token_time'
    | 'trace_id'
    | 'dotted_order'
    | 'last_queued_at'
    | 'feedback_stats'
    | 'child_run_ids'
    | 'parent_run_ids'
    | 'tags'
    | 'in_dataset'
    | 'app_path'
    | 'share_token'
    | 'trace_tier'
    | 'trace_first_received_at'
    | 'ttl_seconds'
    | 'trace_upgrade'
    | 'thread_id'
    | 'trace_min_max_start_time'
    | 'messages'
    | 'inserted_at'
  >;

  session?: Array<string> | null;

  skip_pagination?: boolean | null;

  skip_prev_cursor?: boolean;

  start_time?: string | null;

  trace?: string | null;

  trace_filter?: string | null;

  tree_filter?: string | null;

  use_experimental_search?: boolean;
}

export interface RunStatsParams {
  id?: Array<string> | null;

  /**
   * Enum for run data source types.
   */
  data_source_type?: RunsFilterDataSourceTypeEnum | null;

  end_time?: string | null;

  error?: boolean | null;

  execution_order?: number | null;

  filter?: string | null;

  /**
   * Group by param for run stats.
   */
  group_by?: SessionsAPI.RunStatsGroupBy | null;

  groups?: Array<string | null> | null;

  is_root?: boolean | null;

  parent_run?: string | null;

  query?: string | null;

  reference_example?: Array<string> | null;

  /**
   * Enum for run types.
   */
  run_type?: RunTypeEnum | null;

  search_filter?: string | null;

  select?: Array<
    | 'run_count'
    | 'latency_p50'
    | 'latency_p99'
    | 'latency_avg'
    | 'first_token_p50'
    | 'first_token_p99'
    | 'total_tokens'
    | 'prompt_tokens'
    | 'completion_tokens'
    | 'median_tokens'
    | 'completion_tokens_p50'
    | 'prompt_tokens_p50'
    | 'tokens_p99'
    | 'completion_tokens_p99'
    | 'prompt_tokens_p99'
    | 'last_run_start_time'
    | 'feedback_stats'
    | 'thread_feedback_stats'
    | 'run_facets'
    | 'error_rate'
    | 'streaming_rate'
    | 'total_cost'
    | 'prompt_cost'
    | 'completion_cost'
    | 'cost_p50'
    | 'cost_p99'
    | 'session_feedback_stats'
    | 'all_run_stats'
    | 'all_token_stats'
    | 'group_count'
    | 'prompt_token_details'
    | 'completion_token_details'
    | 'prompt_cost_details'
    | 'completion_cost_details'
  > | null;

  session?: Array<string> | null;

  skip_pagination?: boolean | null;

  start_time?: string | null;

  trace?: string | null;

  trace_filter?: string | null;

  tree_filter?: string | null;

  use_experimental_search?: boolean;
}

Runs.Rules = Rules;

export declare namespace Runs {
  export {
    type BodyParamsForRunSchema as BodyParamsForRunSchema,
    type RequestBodyForRunsGenerateQuery as RequestBodyForRunsGenerateQuery,
    type ResponseBodyForRunsGenerateQuery as ResponseBodyForRunsGenerateQuery,
    type Run as Run,
    type RunSchema as RunSchema,
    type RunStatsQueryParams as RunStatsQueryParams,
    type RunTypeEnum as RunTypeEnum,
    type RunsFilterDataSourceTypeEnum as RunsFilterDataSourceTypeEnum,
    type RunCreateResponse as RunCreateResponse,
    type RunUpdateResponse as RunUpdateResponse,
    type RunIngestBatchResponse as RunIngestBatchResponse,
    type RunQueryResponse as RunQueryResponse,
    type RunStatsResponse as RunStatsResponse,
    type RunUpdate2Response as RunUpdate2Response,
    type RunCreateParams as RunCreateParams,
    type RunRetrieveParams as RunRetrieveParams,
    type RunUpdateParams as RunUpdateParams,
    type RunIngestBatchParams as RunIngestBatchParams,
    type RunQueryParams as RunQueryParams,
    type RunStatsParams as RunStatsParams,
  };

  export { Rules as Rules };
}
