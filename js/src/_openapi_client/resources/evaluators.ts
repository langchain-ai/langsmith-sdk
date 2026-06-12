// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Evaluators extends APIResource {
  /**
   * List all run rules.
   */
  list(
    query: EvaluatorListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<EvaluatorListResponse> {
    return this._client.get('/api/v1/runs/rules', { query, ...options });
  }
}

export interface CodeEvaluatorTopLevel {
  code: string;

  language?: 'python' | 'javascript' | null;
}

/**
 * Run rules schema.
 */
export interface Evaluator {
  id: string;

  created_at: string;

  display_name: string;

  evaluator_version: number;

  sampling_rate: number;

  tenant_id: string;

  updated_at: string;

  webhooks: Array<EvaluatorWebhook> | null;

  add_to_annotation_queue_id?: string | null;

  add_to_annotation_queue_name?: string | null;

  add_to_dataset_id?: string | null;

  add_to_dataset_name?: string | null;

  add_to_dataset_prefer_correction?: boolean;

  alerts?: Array<EvaluatorPagerdutyAlert> | null;

  alignment_annotation_queue_id?: string | null;

  backfill_completed_at?: string | null;

  backfill_error?: string | null;

  backfill_from?: string | null;

  backfill_id?: string | null;

  backfill_progress?: number | null;

  backfill_status?: string | null;

  code_evaluators?: Array<CodeEvaluatorTopLevel> | null;

  corrections_dataset_id?: string | null;

  dataset_id?: string | null;

  dataset_name?: string | null;

  evaluator_id?: string | null;

  evaluators?: Array<EvaluatorTopLevel> | null;

  extend_evaluator_trace_retention?: boolean | null;

  extend_only?: boolean;

  filter?: string | null;

  group_by?: 'thread_id' | null;

  include_extended_stats?: boolean;

  is_enabled?: boolean;

  num_few_shot_examples?: number | null;

  session_id?: string | null;

  session_name?: string | null;

  spend_limit?: Evaluator.SpendLimit | null;

  spend_usd?: number | null;

  trace_count?: number | null;

  trace_filter?: string | null;

  transient?: boolean;

  tree_filter?: string | null;

  use_corrections_dataset?: boolean;
}

export namespace Evaluator {
  export interface SpendLimit {
    limit_usd: string;

    window: 'weekly';
  }
}

export interface EvaluatorPagerdutyAlert {
  routing_key: string;

  /**
   * Enum for severity.
   */
  severity?: 'critical' | 'warning' | 'error' | 'info' | null;

  summary?: string | null;

  /**
   * Enum for alert types.
   */
  type?: 'pagerduty' | null;
}

export interface EvaluatorTopLevel {
  /**
   * Evaluator structured output schema.
   */
  structured: EvaluatorTopLevel.Structured;
}

export namespace EvaluatorTopLevel {
  /**
   * Evaluator structured output schema.
   */
  export interface Structured {
    hub_ref?: string | null;

    model?: { [key: string]: unknown } | null;

    prompt?: Array<Array<unknown>> | null;

    schema?: { [key: string]: unknown } | null;

    template_format?: string | null;

    variable_mapping?: { [key: string]: string } | null;
  }
}

export interface EvaluatorWebhook {
  url: string;

  headers?: { [key: string]: string } | null;
}

export type EvaluatorListResponse = Array<Evaluator>;

export interface EvaluatorListParams {
  id?: Array<string> | null;

  dataset_id?: string | null;

  evaluator_id?: string | null;

  include_backfill_progress?: boolean;

  name_contains?: string | null;

  session_id?: string | null;

  tag_value_id?: Array<string> | null;

  type?: 'session' | 'dataset' | null;
}

export declare namespace Evaluators {
  export {
    type CodeEvaluatorTopLevel as CodeEvaluatorTopLevel,
    type Evaluator as Evaluator,
    type EvaluatorPagerdutyAlert as EvaluatorPagerdutyAlert,
    type EvaluatorTopLevel as EvaluatorTopLevel,
    type EvaluatorWebhook as EvaluatorWebhook,
    type EvaluatorListResponse as EvaluatorListResponse,
    type EvaluatorListParams as EvaluatorListParams,
  };
}
