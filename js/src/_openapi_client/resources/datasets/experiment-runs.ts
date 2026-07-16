// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RunsAPI from '../runs.js';
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
  query(
    datasetID: string,
    body: ExperimentRunQueryParams,
    options?: RequestOptions,
  ): PagePromise<ExperimentRunQueryResponsesItemsCursorPostPagination, ExperimentRunQueryResponse> {
    return this._client.getAPIList(
      path`/v2/datasets/${datasetID}/experiment-runs`,
      ItemsCursorPostPagination<ExperimentRunQueryResponse>,
      { body, method: 'post', ...options },
    );
  }
}

export type ExperimentRunQueryResponsesItemsCursorPostPagination =
  ItemsCursorPostPagination<ExperimentRunQueryResponse>;

export interface ExperimentRunQueryResponse {
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

export interface ExperimentRunQueryParams extends ItemsCursorPostPaginationParams {
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
  selects?: Array<RunsAPI.RunSelectField>;

  /**
   * `sort` controls feedback-score sorting (single project only).
   */
  sort?: ExperimentRunQueryParams.Sort;
}

export namespace ExperimentRunQueryParams {
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
    type ExperimentRunQueryResponse as ExperimentRunQueryResponse,
    type ExperimentRunQueryResponsesItemsCursorPostPagination as ExperimentRunQueryResponsesItemsCursorPostPagination,
    type ExperimentRunQueryParams as ExperimentRunQueryParams,
  };
}
