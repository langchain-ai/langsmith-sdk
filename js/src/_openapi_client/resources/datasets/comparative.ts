// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Comparative extends APIResource {
  /**
   * Create a comparative experiment.
   */
  create(body: ComparativeCreateParams, options?: RequestOptions): APIPromise<ComparativeCreateResponse> {
    return this._client.post('/api/v1/datasets/comparative', { body, ...options });
  }

  /**
   * Delete a specific comparative experiment.
   */
  delete(comparativeExperimentID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/datasets/comparative/${comparativeExperimentID}`, options);
  }
}

/**
 * Simple experiment info schema for use with comparative experiments
 */
export interface SimpleExperimentInfo {
  id: string;

  name: string;
}

/**
 * Enum for available comparative experiment columns to sort by.
 */
export type SortByComparativeExperimentColumn = 'name' | 'created_at';

/**
 * ComparativeExperiment schema.
 */
export interface ComparativeCreateResponse {
  id: string;

  created_at: string;

  modified_at: string;

  reference_dataset_id: string;

  tenant_id: string;

  description?: string | null;

  extra?: { [key: string]: unknown } | null;

  name?: string | null;
}

export type ComparativeDeleteResponse = unknown;

export interface ComparativeCreateParams {
  experiment_ids: Array<string>;

  id?: string;

  created_at?: string;

  description?: string | null;

  extra?: { [key: string]: unknown } | null;

  modified_at?: string;

  name?: string | null;

  reference_dataset_id?: string | null;
}

export declare namespace Comparative {
  export {
    type SimpleExperimentInfo as SimpleExperimentInfo,
    type SortByComparativeExperimentColumn as SortByComparativeExperimentColumn,
    type ComparativeCreateResponse as ComparativeCreateResponse,
    type ComparativeDeleteResponse as ComparativeDeleteResponse,
    type ComparativeCreateParams as ComparativeCreateParams,
  };
}
