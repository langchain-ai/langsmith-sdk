// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Experiments extends APIResource {
  /**
   * Stream grouped and aggregated experiments.
   */
  grouped(datasetID: string, body: ExperimentGroupedParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post(path`/api/v1/datasets/${datasetID}/experiments/grouped`, { body, ...options });
  }
}

export type ExperimentGroupedResponse = unknown;

export interface ExperimentGroupedParams {
  metadata_keys: Array<string>;

  dataset_version?: string | null;

  experiment_limit?: number;

  filter?: string | null;

  name_contains?: string | null;

  stats_start_time?: string | null;

  tag_value_id?: Array<string> | null;

  use_approx_stats?: boolean;
}

export declare namespace Experiments {
  export {
    type ExperimentGroupedResponse as ExperimentGroupedResponse,
    type ExperimentGroupedParams as ExperimentGroupedParams,
  };
}
