// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Splits extends APIResource {
  /**
   * Update Dataset Splits
   */
  create(
    datasetID: string,
    body: SplitCreateParams,
    options?: RequestOptions,
  ): APIPromise<SplitCreateResponse> {
    return this._client.put(path`/api/v1/datasets/${datasetID}/splits`, { body, ...options });
  }

  /**
   * Get Dataset Splits
   */
  retrieve(
    datasetID: string,
    query: SplitRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<SplitRetrieveResponse> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/splits`, { query, ...options });
  }
}

export type SplitCreateResponse = Array<string>;

export type SplitRetrieveResponse = Array<string>;

export interface SplitCreateParams {
  examples: Array<string>;

  split_name: string;

  remove?: boolean;
}

export interface SplitRetrieveParams {
  /**
   * Only modifications made on or before this time are included. If None, the latest
   * version of the dataset is used.
   */
  as_of?: (string & {}) | string;
}

export declare namespace Splits {
  export {
    type SplitCreateResponse as SplitCreateResponse,
    type SplitRetrieveResponse as SplitRetrieveResponse,
    type SplitCreateParams as SplitCreateParams,
    type SplitRetrieveParams as SplitRetrieveParams,
  };
}
