// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as RunsAPI from './runs';
import {
  RunCreateParams,
  RunCreateResponse,
  RunDeleteAllParams,
  RunDeleteAllResponse,
  RunDeleteQueueParams,
  RunDeleteQueueResponse,
  RunListParams,
  RunListResponse,
  RunUpdateParams,
  RunUpdateResponse,
  Runs,
} from './runs';
import * as DatasetsAPI from '../datasets/datasets';
import { APIPromise } from '../../core/api-promise';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';
import * as RunsAPI_ from '../runs/runs';

export class AnnotationQueues extends APIResource {
  runs: RunsAPI.Runs = new RunsAPI.Runs(this._client);

  /**
   * Get Annotation Queue
   */
  retrieve(queueID: string, options?: RequestOptions): APIPromise<AnnotationQueueRetrieveResponse> {
    return this._client.get(path`/api/v1/annotation-queues/${queueID}`, options);
  }

  /**
   * Update Annotation Queue
   */
  update(queueID: string, body: AnnotationQueueUpdateParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.patch(path`/api/v1/annotation-queues/${queueID}`, { body, ...options });
  }

  /**
   * Delete Annotation Queue
   */
  delete(queueID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/annotation-queues/${queueID}`, options);
  }

  /**
   * Create Annotation Queue
   */
  annotationQueues(
    body: AnnotationQueueAnnotationQueuesParams,
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueSchema> {
    return this._client.post('/api/v1/annotation-queues', { body, ...options });
  }

  /**
   * Create Identity Annotation Queue Run Status
   */
  createRunStatus(
    annotationQueueRunID: string,
    body: AnnotationQueueCreateRunStatusParams,
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.post(path`/api/v1/annotation-queues/status/${annotationQueueRunID}`, {
      body,
      ...options,
    });
  }

  /**
   * Export Annotation Queue Archived Runs
   */
  export(queueID: string, body: AnnotationQueueExportParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post(path`/api/v1/annotation-queues/${queueID}/export`, { body, ...options });
  }

  /**
   * Populate annotation queue with runs from an experiment.
   */
  populate(body: AnnotationQueuePopulateParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post('/api/v1/annotation-queues/populate', { body, ...options });
  }

  /**
   * Get Annotation Queues
   */
  retrieveAnnotationQueues(
    query: AnnotationQueueRetrieveAnnotationQueuesParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<
    AnnotationQueueRetrieveAnnotationQueuesResponsesOffsetPaginationTopLevelArray,
    AnnotationQueueRetrieveAnnotationQueuesResponse
  > {
    return this._client.getAPIList(
      '/api/v1/annotation-queues',
      OffsetPaginationTopLevelArray<AnnotationQueueRetrieveAnnotationQueuesResponse>,
      { query, ...options },
    );
  }

  /**
   * Get Annotation Queues For Run
   */
  retrieveQueues(runID: string, options?: RequestOptions): APIPromise<AnnotationQueueRetrieveQueuesResponse> {
    return this._client.get(path`/api/v1/annotation-queues/${runID}/queues`, options);
  }

  /**
   * Get a run from an annotation queue
   */
  retrieveRun(
    index: number,
    params: AnnotationQueueRetrieveRunParams,
    options?: RequestOptions,
  ): APIPromise<RunSchemaWithAnnotationQueueInfo> {
    const { queue_id, ...query } = params;
    return this._client.get(path`/api/v1/annotation-queues/${queue_id}/run/${index}`, { query, ...options });
  }

  /**
   * Get Size From Annotation Queue
   */
  retrieveSize(
    queueID: string,
    query: AnnotationQueueRetrieveSizeParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueSizeSchema> {
    return this._client.get(path`/api/v1/annotation-queues/${queueID}/size`, { query, ...options });
  }

  /**
   * Get Total Archived From Annotation Queue
   */
  retrieveTotalArchived(
    queueID: string,
    query: AnnotationQueueRetrieveTotalArchivedParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<AnnotationQueueSizeSchema> {
    return this._client.get(path`/api/v1/annotation-queues/${queueID}/total_archived`, { query, ...options });
  }

  /**
   * Get Total Size From Annotation Queue
   */
  retrieveTotalSize(queueID: string, options?: RequestOptions): APIPromise<AnnotationQueueSizeSchema> {
    return this._client.get(path`/api/v1/annotation-queues/${queueID}/total_size`, options);
  }
}

export type AnnotationQueueRetrieveAnnotationQueuesResponsesOffsetPaginationTopLevelArray =
  OffsetPaginationTopLevelArray<AnnotationQueueRetrieveAnnotationQueuesResponse>;

export interface AnnotationQueueRubricItemSchema {
  feedback_key: string;

  description?: string | null;

  is_assertion?: boolean | null;

  is_required?: boolean | null;

  score_descriptions?: { [key: string]: string } | null;

  value_descriptions?: { [key: string]: string } | null;
}

/**
 * AnnotationQueue schema.
 */
export interface AnnotationQueueSchema {
  id: string;

  name: string;

  queue_type: 'single' | 'pairwise';

  tenant_id: string;

  assigned_reviewers?: Array<AnnotationQueueSchema.AssignedReviewer>;

  created_at?: string;

  default_dataset?: string | null;

  description?: string | null;

  enable_reservations?: boolean | null;

  metadata?: { [key: string]: unknown } | null;

  num_reviewers_per_item?: number | null;

  reservation_minutes?: number | null;

  reviewer_access_mode?: string;

  run_rule_id?: string | null;

  source_rule_id?: string | null;

  updated_at?: string;
}

export namespace AnnotationQueueSchema {
  /**
   * Identity info for an assigned reviewer on an annotation queue.
   */
  export interface AssignedReviewer {
    id: string;

    email?: string | null;

    name?: string | null;
  }
}

/**
 * Size of an Annotation Queue
 */
export interface AnnotationQueueSizeSchema {
  size: number;
}

/**
 * Run schema with annotation queue info.
 */
export interface RunSchemaWithAnnotationQueueInfo {
  id: string;

  app_path: string;

  dotted_order: string;

  name: string;

  queue_run_id: string;

  /**
   * Enum for run types.
   */
  run_type: RunsAPI_.RunTypeEnum;

  session_id: string;

  status: string;

  trace_id: string;

  added_at?: string | null;

  child_run_ids?: Array<string> | null;

  completed_by?: Array<string>;

  completion_cost?: string | null;

  completion_cost_details?: { [key: string]: string } | null;

  completion_token_details?: { [key: string]: number } | null;

  completion_tokens?: number;

  direct_child_run_ids?: Array<string> | null;

  effective_added_at?: string | null;

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

  last_reviewed_time?: string | null;

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

  reserved_by?: Array<string>;

  s3_urls?: { [key: string]: unknown } | null;

  serialized?: { [key: string]: unknown } | null;

  share_token?: string | null;

  source_proposed_example_id?: string | null;

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
 * AnnotationQueue schema with rubric.
 */
export interface AnnotationQueueRetrieveResponse {
  id: string;

  name: string;

  queue_type: 'single' | 'pairwise';

  tenant_id: string;

  assigned_reviewers?: Array<AnnotationQueueRetrieveResponse.AssignedReviewer>;

  created_at?: string;

  default_dataset?: string | null;

  description?: string | null;

  enable_reservations?: boolean | null;

  metadata?: { [key: string]: unknown } | null;

  num_reviewers_per_item?: number | null;

  reservation_minutes?: number | null;

  reviewer_access_mode?: string;

  rubric_instructions?: string | null;

  rubric_items?: Array<AnnotationQueueRubricItemSchema> | null;

  run_rule_id?: string | null;

  source_rule_id?: string | null;

  updated_at?: string;
}

export namespace AnnotationQueueRetrieveResponse {
  /**
   * Identity info for an assigned reviewer on an annotation queue.
   */
  export interface AssignedReviewer {
    id: string;

    email?: string | null;

    name?: string | null;
  }
}

export type AnnotationQueueUpdateResponse = unknown;

export type AnnotationQueueDeleteResponse = unknown;

export type AnnotationQueueCreateRunStatusResponse = unknown;

export type AnnotationQueueExportResponse = unknown;

export type AnnotationQueuePopulateResponse = unknown;

/**
 * AnnotationQueue schema with size.
 */
export interface AnnotationQueueRetrieveAnnotationQueuesResponse {
  id: string;

  name: string;

  queue_type: 'single' | 'pairwise';

  tenant_id: string;

  total_runs: number;

  assigned_reviewers?: Array<AnnotationQueueRetrieveAnnotationQueuesResponse.AssignedReviewer>;

  created_at?: string;

  default_dataset?: string | null;

  description?: string | null;

  enable_reservations?: boolean | null;

  metadata?: { [key: string]: unknown } | null;

  num_reviewers_per_item?: number | null;

  reservation_minutes?: number | null;

  reviewer_access_mode?: string;

  run_rule_id?: string | null;

  source_rule_id?: string | null;

  updated_at?: string;
}

export namespace AnnotationQueueRetrieveAnnotationQueuesResponse {
  /**
   * Identity info for an assigned reviewer on an annotation queue.
   */
  export interface AssignedReviewer {
    id: string;

    email?: string | null;

    name?: string | null;
  }
}

export type AnnotationQueueRetrieveQueuesResponse = Array<AnnotationQueueSchema>;

export interface AnnotationQueueUpdateParams {
  default_dataset?: string | null;

  description?: string | null;

  enable_reservations?: boolean;

  metadata?: { [key: string]: unknown } | DatasetsAPI.Missing | null;

  name?: string | null;

  num_reviewers_per_item?: number | DatasetsAPI.Missing | null;

  reservation_minutes?: number | null;

  reviewer_access_mode?: 'any' | 'assigned' | null;

  rubric_instructions?: string | null;

  rubric_items?: Array<AnnotationQueueRubricItemSchema> | null;
}

export interface AnnotationQueueAnnotationQueuesParams {
  name: string;

  id?: string;

  created_at?: string;

  default_dataset?: string | null;

  description?: string | null;

  enable_reservations?: boolean | null;

  metadata?: { [key: string]: unknown } | null;

  num_reviewers_per_item?: number | null;

  reservation_minutes?: number | null;

  reviewer_access_mode?: string;

  rubric_instructions?: string | null;

  rubric_items?: Array<AnnotationQueueRubricItemSchema> | null;

  session_ids?: Array<string> | null;

  updated_at?: string;
}

export interface AnnotationQueueCreateRunStatusParams {
  override_added_at?: string | null;

  status?: string | null;
}

export interface AnnotationQueueExportParams {
  end_time?: string | null;

  include_annotator_detail?: boolean;

  start_time?: string | null;
}

export interface AnnotationQueuePopulateParams {
  queue_id: string;

  session_ids: Array<string>;
}

export interface AnnotationQueueRetrieveAnnotationQueuesParams extends OffsetPaginationTopLevelArrayParams {
  assigned_to_me?: boolean;

  dataset_id?: string | null;

  ids?: Array<string> | null;

  name?: string | null;

  name_contains?: string | null;

  queue_type?: 'single' | 'pairwise' | null;

  sort_by?: string | null;

  sort_by_desc?: boolean;

  tag_value_id?: Array<string> | null;
}

export interface AnnotationQueueRetrieveRunParams {
  /**
   * Path param
   */
  queue_id: string;

  /**
   * Query param
   */
  include_extra?: boolean;
}

export interface AnnotationQueueRetrieveSizeParams {
  status?: 'needs_my_review' | 'needs_others_review' | 'completed' | null;
}

export interface AnnotationQueueRetrieveTotalArchivedParams {
  end_time?: string | null;

  start_time?: string | null;
}

AnnotationQueues.Runs = Runs;

export declare namespace AnnotationQueues {
  export {
    type AnnotationQueueRubricItemSchema as AnnotationQueueRubricItemSchema,
    type AnnotationQueueSchema as AnnotationQueueSchema,
    type AnnotationQueueSizeSchema as AnnotationQueueSizeSchema,
    type RunSchemaWithAnnotationQueueInfo as RunSchemaWithAnnotationQueueInfo,
    type AnnotationQueueRetrieveResponse as AnnotationQueueRetrieveResponse,
    type AnnotationQueueUpdateResponse as AnnotationQueueUpdateResponse,
    type AnnotationQueueDeleteResponse as AnnotationQueueDeleteResponse,
    type AnnotationQueueCreateRunStatusResponse as AnnotationQueueCreateRunStatusResponse,
    type AnnotationQueueExportResponse as AnnotationQueueExportResponse,
    type AnnotationQueuePopulateResponse as AnnotationQueuePopulateResponse,
    type AnnotationQueueRetrieveAnnotationQueuesResponse as AnnotationQueueRetrieveAnnotationQueuesResponse,
    type AnnotationQueueRetrieveQueuesResponse as AnnotationQueueRetrieveQueuesResponse,
    type AnnotationQueueRetrieveAnnotationQueuesResponsesOffsetPaginationTopLevelArray as AnnotationQueueRetrieveAnnotationQueuesResponsesOffsetPaginationTopLevelArray,
    type AnnotationQueueUpdateParams as AnnotationQueueUpdateParams,
    type AnnotationQueueAnnotationQueuesParams as AnnotationQueueAnnotationQueuesParams,
    type AnnotationQueueCreateRunStatusParams as AnnotationQueueCreateRunStatusParams,
    type AnnotationQueueExportParams as AnnotationQueueExportParams,
    type AnnotationQueuePopulateParams as AnnotationQueuePopulateParams,
    type AnnotationQueueRetrieveAnnotationQueuesParams as AnnotationQueueRetrieveAnnotationQueuesParams,
    type AnnotationQueueRetrieveRunParams as AnnotationQueueRetrieveRunParams,
    type AnnotationQueueRetrieveSizeParams as AnnotationQueueRetrieveSizeParams,
    type AnnotationQueueRetrieveTotalArchivedParams as AnnotationQueueRetrieveTotalArchivedParams,
  };

  export {
    Runs as Runs,
    type RunCreateResponse as RunCreateResponse,
    type RunUpdateResponse as RunUpdateResponse,
    type RunListResponse as RunListResponse,
    type RunDeleteAllResponse as RunDeleteAllResponse,
    type RunDeleteQueueResponse as RunDeleteQueueResponse,
    type RunCreateParams as RunCreateParams,
    type RunUpdateParams as RunUpdateParams,
    type RunListParams as RunListParams,
    type RunDeleteAllParams as RunDeleteAllParams,
    type RunDeleteQueueParams as RunDeleteQueueParams,
  };
}
