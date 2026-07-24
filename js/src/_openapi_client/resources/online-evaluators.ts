// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import {
  OffsetPaginationOnlineEvaluators,
  type OffsetPaginationOnlineEvaluatorsParams,
  PagePromise,
} from '../core/pagination.js';
import { buildHeaders } from '../internal/headers.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class OnlineEvaluators extends APIResource {
  /**
   * Create a new LLM or code evaluator for the current workspace.
   */
  create(
    body: OnlineEvaluatorCreateParams,
    options?: RequestOptions,
  ): APIPromise<CreateOnlineEvaluatorResponse> {
    return this._client.post('/v1/platform/evaluators', { body, ...options });
  }

  /**
   * Retrieve a single evaluator by its ID.
   */
  retrieve(evaluatorID: string, options?: RequestOptions): APIPromise<OnlineEvaluator> {
    return this._client.get(path`/v1/platform/evaluators/${evaluatorID}`, options);
  }

  /**
   * Update an existing evaluator's name, LLM configuration, or code configuration.
   */
  update(
    evaluatorID: string,
    body: OnlineEvaluatorUpdateParams,
    options?: RequestOptions,
  ): APIPromise<UpdateOnlineEvaluatorResponse> {
    return this._client.patch(path`/v1/platform/evaluators/${evaluatorID}`, { body, ...options });
  }

  /**
   * List evaluators for the current workspace, with optional filtering by type,
   * name, tag, feedback key, or resource ID.
   */
  list(
    query: OnlineEvaluatorListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<OnlineEvaluatorsOffsetPaginationOnlineEvaluators, OnlineEvaluator> {
    return this._client.getAPIList(
      '/v1/platform/evaluators',
      OffsetPaginationOnlineEvaluators<OnlineEvaluator>,
      { query, ...options },
    );
  }

  /**
   * Delete an evaluator. When delete_run_rules is true, all run rules referencing
   * this evaluator are deleted first (same tenant). Associated llm_evaluators and
   * code_evaluators rows are removed by foreign-key cascade when the evaluator row
   * is deleted.
   */
  delete(
    evaluatorID: string,
    params: OnlineEvaluatorDeleteParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<void> {
    const { delete_run_rules } = params ?? {};
    return this._client.delete(path`/v1/platform/evaluators/${evaluatorID}`, {
      query: { delete_run_rules },
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }

  /**
   * Delete multiple evaluators by their IDs. Returns per-item success/failure.
   */
  bulkDelete(
    params: OnlineEvaluatorBulkDeleteParams,
    options?: RequestOptions,
  ): APIPromise<BulkDeleteEvaluatorsResponse> {
    const { evaluator_ids, delete_run_rules } = params;
    return this._client.delete('/v1/platform/evaluators', {
      query: { evaluator_ids, delete_run_rules },
      ...options,
    });
  }

  /**
   * Returns per-day LLM evaluator spend for the requested 7-day period, grouped by
   * evaluator, resource, or run rule. Exactly one of group_by, evaluator_id,
   * session_id, or dataset_id is required. resource_id, type, and feedback_key may
   * be supplied with group_by to narrow listing aggregations.
   */
  spend(
    query: OnlineEvaluatorSpendParams,
    options?: RequestOptions,
  ): APIPromise<GetOnlineEvaluatorSpendResponse> {
    return this._client.get('/v1/platform/evaluators/spend', { query, ...options });
  }
}

export type OnlineEvaluatorsOffsetPaginationOnlineEvaluators =
  OffsetPaginationOnlineEvaluators<OnlineEvaluator>;

export interface BulkDeleteEvaluatorFailedItem {
  id?: string;

  error?: string;
}

export interface BulkDeleteEvaluatorsResponse {
  failed?: Array<BulkDeleteEvaluatorFailedItem>;

  succeeded?: Array<string>;
}

export interface CreateOnlineCodeEvaluatorRequest {
  code?: string;

  /**
   * Default: "python"
   */
  language?: string;
}

export interface CreateOnlineEvaluatorRequest {
  code_evaluator?: CreateOnlineCodeEvaluatorRequest;

  llm_evaluator?: CreateOnlineLlmEvaluatorRequest;

  name?: string;

  type?: OnlineEvaluatorType;
}

export interface CreateOnlineEvaluatorResponse {
  evaluator?: OnlineEvaluator;
}

export interface CreateOnlineLlmEvaluatorRequest {
  commit_hash_or_tag?: string;

  prompt_repo_handle?: string;

  variable_mapping?: unknown;
}

export interface GetOnlineEvaluatorSpendResponse {
  groups?: Array<OnlineEvaluatorSpendGroup>;

  period_end?: string;

  period_start?: string;
}

export interface OnlineCodeEvaluator {
  code?: string;

  evaluator_id?: string;

  /**
   * Default: "python"
   */
  language?: string;
}

export interface OnlineEvaluator {
  id?: string;

  code_evaluator?: OnlineCodeEvaluator;

  created_at?: string;

  created_by?: string;

  feedback_keys?: Array<string>;

  /**
   * IsManaged marks a LangChain-managed evaluator (currently the managed Perceived
   * Error judge). NULL in the DB is read as false via COALESCE.
   */
  is_managed?: boolean;

  /**
   * Embedded child evaluator (populated based on type)
   */
  llm_evaluator?: OnlineLlmEvaluator;

  name?: string;

  run_rules?: Array<OnlineEvaluatorRunRule>;

  tenant_id?: string;

  type?: OnlineEvaluatorType;

  updated_at?: string;
}

export interface OnlineEvaluatorRunRule {
  id?: string;

  corrections_dataset_id?: string;

  dataset_id?: string;

  dataset_name?: string;

  group_by?: string;

  num_few_shot_examples?: number;

  session_id?: string;

  session_name?: string;

  /**
   * SpendLimit is the effective spend-cap limit for this rule (nil when
   * unconfigured).
   */
  spend_limit?: OnlineSpendLimit;

  /**
   * Per-rule usage for the current ISO week (omitted when feature is disabled).
   * LLM-evaluator rules are initialized to 0; code-evaluator rules include trace
   * counts only.
   */
  spend_usd?: number;

  trace_count?: number;

  use_corrections_dataset?: boolean;
}

export interface OnlineEvaluatorSpendDay {
  date?: string;

  spend_usd?: number;

  trace_count?: number;
}

export interface OnlineEvaluatorSpendGroup {
  dataset_id?: string;

  dataset_name?: string;

  days?: Array<OnlineEvaluatorSpendDay>;

  evaluator_id?: string;

  evaluator_name?: string;

  prev_total_spend_usd?: number;

  prev_total_trace_count?: number;

  run_rule_id?: string;

  run_rule_name?: string;

  session_id?: string;

  session_name?: string;

  spend_limit?: OnlineSpendLimit;

  total_spend_usd?: number;

  total_trace_count?: number;
}

export type OnlineEvaluatorType = 'llm' | 'code';

export interface OnlineLlmEvaluator {
  annotation_queue_id?: string;

  commit_hash_or_tag?: string;

  corrections_dataset_id?: string;

  evaluator_id?: string;

  num_few_shot_examples?: number;

  prompt_id?: string;

  prompt_repo_handle?: string;

  /**
   * Derived from the evaluator's run rules — shared across all rules on this
   * evaluator. Nil when the evaluator has no run rules.
   */
  use_corrections_dataset?: boolean;

  /**
   * JSONB
   */
  variable_mapping?: unknown;
}

export interface OnlineSpendLimit {
  limit_usd?: number;

  utilization_pct?: number;

  window?: string;
}

export interface UpdateOnlineCodeEvaluatorRequest {
  code?: string;

  language?: string;
}

export interface UpdateOnlineEvaluatorRequest {
  code_evaluator?: UpdateOnlineCodeEvaluatorRequest;

  llm_evaluator?: UpdateOnlineLlmEvaluatorRequest;

  name?: string;
}

export interface UpdateOnlineEvaluatorResponse {
  evaluator?: OnlineEvaluator;
}

export interface UpdateOnlineLlmEvaluatorRequest {
  commit_hash_or_tag?: string;

  num_few_shot_examples?: number;

  prompt_repo_handle?: string;

  use_corrections_dataset?: boolean;

  variable_mapping?: unknown;
}

export interface OnlineEvaluatorCreateParams {
  code_evaluator?: CreateOnlineCodeEvaluatorRequest;

  llm_evaluator?: CreateOnlineLlmEvaluatorRequest;

  name?: string;

  type?: OnlineEvaluatorType;
}

export interface OnlineEvaluatorUpdateParams {
  code_evaluator?: UpdateOnlineCodeEvaluatorRequest;

  llm_evaluator?: UpdateOnlineLlmEvaluatorRequest;

  name?: string;
}

export interface OnlineEvaluatorListParams extends OffsetPaginationOnlineEvaluatorsParams {
  /**
   * Filter by feedback key
   */
  feedback_key?: string;

  /**
   * Filter by name substring (also searches creator names)
   */
  name_contains?: string;

  /**
   * Filter by resource IDs
   */
  resource_id?: Array<string>;

  /**
   * Field to sort by
   */
  sort_by?: string;

  /**
   * Sort in descending order
   */
  sort_by_desc?: boolean;

  /**
   * Filter by tag value IDs
   */
  tag_value_id?: Array<string>;

  /**
   * Filter by evaluator type
   */
  type?: string;
}

export interface OnlineEvaluatorDeleteParams {
  /**
   * When true, delete all run rules for this evaluator before deleting the evaluator
   */
  delete_run_rules?: boolean;
}

export interface OnlineEvaluatorBulkDeleteParams {
  /**
   * Evaluator IDs to delete
   */
  evaluator_ids: Array<string>;

  /**
   * When true, delete all run rules for this evaluator before deleting the evaluator
   */
  delete_run_rules?: boolean;
}

export interface OnlineEvaluatorSpendParams {
  /**
   * Start of the 7-day window (YYYY-MM-DD).
   */
  period_start: string;

  /**
   * Filter to a specific dataset (UUID). Mutually exclusive with group_by.
   */
  dataset_id?: string;

  /**
   * Filter to a specific evaluator (UUID). Mutually exclusive with group_by.
   */
  evaluator_id?: string;

  /**
   * Filter grouped results by evaluator feedback key. Only valid with group_by.
   */
  feedback_key?: string;

  /**
   * Aggregation mode: 'evaluator', 'resource', or 'run_rule'. Mutually exclusive
   * with entity filters.
   */
  group_by?: string;

  /**
   * Filter grouped results to evaluators attached to all supplied project or dataset
   * IDs. Only valid with group_by.
   */
  resource_id?: Array<string>;

  /**
   * Filter to a specific project (UUID). Mutually exclusive with group_by.
   */
  session_id?: string;

  /**
   * Filter grouped results by evaluator type: 'llm' or 'code'. Only valid with
   * group_by.
   */
  type?: string;
}

export declare namespace OnlineEvaluators {
  export {
    type BulkDeleteEvaluatorFailedItem as BulkDeleteEvaluatorFailedItem,
    type BulkDeleteEvaluatorsResponse as BulkDeleteEvaluatorsResponse,
    type CreateOnlineCodeEvaluatorRequest as CreateOnlineCodeEvaluatorRequest,
    type CreateOnlineEvaluatorRequest as CreateOnlineEvaluatorRequest,
    type CreateOnlineEvaluatorResponse as CreateOnlineEvaluatorResponse,
    type CreateOnlineLlmEvaluatorRequest as CreateOnlineLlmEvaluatorRequest,
    type GetOnlineEvaluatorSpendResponse as GetOnlineEvaluatorSpendResponse,
    type OnlineCodeEvaluator as OnlineCodeEvaluator,
    type OnlineEvaluator as OnlineEvaluator,
    type OnlineEvaluatorRunRule as OnlineEvaluatorRunRule,
    type OnlineEvaluatorSpendDay as OnlineEvaluatorSpendDay,
    type OnlineEvaluatorSpendGroup as OnlineEvaluatorSpendGroup,
    type OnlineEvaluatorType as OnlineEvaluatorType,
    type OnlineLlmEvaluator as OnlineLlmEvaluator,
    type OnlineSpendLimit as OnlineSpendLimit,
    type UpdateOnlineCodeEvaluatorRequest as UpdateOnlineCodeEvaluatorRequest,
    type UpdateOnlineEvaluatorRequest as UpdateOnlineEvaluatorRequest,
    type UpdateOnlineEvaluatorResponse as UpdateOnlineEvaluatorResponse,
    type UpdateOnlineLlmEvaluatorRequest as UpdateOnlineLlmEvaluatorRequest,
    type OnlineEvaluatorsOffsetPaginationOnlineEvaluators as OnlineEvaluatorsOffsetPaginationOnlineEvaluators,
    type OnlineEvaluatorCreateParams as OnlineEvaluatorCreateParams,
    type OnlineEvaluatorUpdateParams as OnlineEvaluatorUpdateParams,
    type OnlineEvaluatorListParams as OnlineEvaluatorListParams,
    type OnlineEvaluatorDeleteParams as OnlineEvaluatorDeleteParams,
    type OnlineEvaluatorBulkDeleteParams as OnlineEvaluatorBulkDeleteParams,
    type OnlineEvaluatorSpendParams as OnlineEvaluatorSpendParams,
  };
}
