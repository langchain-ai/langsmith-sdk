// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RunsAPI from '../runs/runs.js';
import {
  ItemsCursorPostPagination,
  type ItemsCursorPostPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class ExperimentRuns extends APIResource {
  /**
   * Returns a paginated page of dataset examples with runs from the requested
   * experiments. Response uses the canonical `{items, next_cursor}` envelope.
   */
  create(
    datasetID: string,
    body: ExperimentRunCreateParams,
    options?: RequestOptions,
  ): PagePromise<ExperimentRunCreateResponsesItemsCursorPostPagination, ExperimentRunCreateResponse> {
    return this._client.getAPIList(
      path`/v2/datasets/${datasetID}/experiment-runs`,
      ItemsCursorPostPagination<ExperimentRunCreateResponse>,
      { body, method: 'post', ...options },
    );
  }
}

export type ExperimentRunCreateResponsesItemsCursorPostPagination =
  ItemsCursorPostPagination<ExperimentRunCreateResponse>;

export interface ExperimentRunCreateResponse {
  /**
   * `id` is the dataset example UUID.
   */
  id?: string;

  /**
   * `attachment_urls` maps each attachment name to a pre-signed download URL.
   */
  attachment_urls?: unknown;

  /**
   * `created_at` is when the example was created (RFC3339 date-time).
   */
  created_at?: string;

  /**
   * `dataset_id` is the parent dataset UUID.
   */
  dataset_id?: string;

  /**
   * `inputs` is the example input payload (arbitrary JSON object).
   */
  inputs?: unknown;

  /**
   * `metadata` is arbitrary user-defined JSON metadata on the example.
   */
  metadata?: unknown;

  /**
   * `modified_at` is when the example was last modified (RFC3339 date-time).
   */
  modified_at?: string;

  /**
   * `name` is the example's optional name.
   */
  name?: string;

  /**
   * `outputs` is the example reference-output payload (arbitrary JSON object).
   */
  outputs?: unknown;

  /**
   * `runs` is the list of experiment runs produced for this example.
   */
  runs?: Array<RunsAPI.Run>;

  /**
   * `source_run_id` is the run UUID the example was created from, if any.
   */
  source_run_id?: string;
}

export interface ExperimentRunCreateParams extends ItemsCursorPostPaginationParams {
  /**
   * `comparative_experiment_id` scopes pairwise-annotation feedback (optional).
   */
  comparative_experiment_id?: string;

  /**
   * `example_ids` optionally restricts the page to these dataset example UUIDs (max
   * 1000).
   */
  example_ids?: Array<string>;

  /**
   * `experiment_ids` lists the experiment (tracing session) UUIDs to query.
   * Required, non-empty.
   */
  experiment_ids?: Array<string>;

  /**
   * `filters` maps a project (session) UUID string to a list of filter expressions
   * (optional).
   */
  filters?: { [key: string]: Array<string> };

  /**
   * `selects` lists which run properties to include. Omitted => only `id`. Tokens
   * mirror /v2/runs/query.
   */
  selects?: Array<
    | 'ID'
    | 'NAME'
    | 'RUN_TYPE'
    | 'STATUS'
    | 'START_TIME'
    | 'END_TIME'
    | 'LATENCY_SECONDS'
    | 'FIRST_TOKEN_TIME'
    | 'ERROR'
    | 'ERROR_PREVIEW'
    | 'EXTRA'
    | 'METADATA'
    | 'EVENTS'
    | 'INPUTS'
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS'
    | 'OUTPUTS_PREVIEW'
    | 'MANIFEST'
    | 'PARENT_RUN_IDS'
    | 'PROJECT_ID'
    | 'TRACE_ID'
    | 'THREAD_ID'
    | 'DOTTED_ORDER'
    | 'IS_ROOT'
    | 'REFERENCE_EXAMPLE_ID'
    | 'REFERENCE_DATASET_ID'
    | 'TOTAL_TOKENS'
    | 'PROMPT_TOKENS'
    | 'COMPLETION_TOKENS'
    | 'TOTAL_COST'
    | 'PROMPT_COST'
    | 'COMPLETION_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'PRICE_MODEL_ID'
    | 'TAGS'
    | 'APP_PATH'
    | 'ATTACHMENTS'
    | 'THREAD_EVALUATION_TIME'
    | 'IS_IN_DATASET'
    | 'SHARE_URL'
    | 'FEEDBACK_STATS'
  >;

  /**
   * `sort` controls feedback-score sorting (single project only).
   */
  sort?: ExperimentRunCreateParams.Sort;
}

export namespace ExperimentRunCreateParams {
  /**
   * `sort` controls feedback-score sorting (single project only).
   */
  export interface Sort {
    /**
     * `by` is the feedback selector, e.g. `feedback.correctness` (the `feedback.`
     * prefix is optional).
     */
    by?: string;

    /**
     * `order` is `ASC` or `DESC` (defaults to `DESC`).
     */
    order?: string;
  }
}

export declare namespace ExperimentRuns {
  export {
    type ExperimentRunCreateResponse as ExperimentRunCreateResponse,
    type ExperimentRunCreateResponsesItemsCursorPostPagination as ExperimentRunCreateResponsesItemsCursorPostPagination,
    type ExperimentRunCreateParams as ExperimentRunCreateParams,
  };
}
