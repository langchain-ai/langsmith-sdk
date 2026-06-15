// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as DatasetsAPI from './datasets.js';
import { DatasetVersionsOffsetPaginationTopLevelArray } from './datasets.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Versions extends APIResource {
  /**
   * Get dataset versions.
   */
  list(
    datasetID: string,
    query: VersionListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<DatasetVersionsOffsetPaginationTopLevelArray, DatasetsAPI.DatasetVersion> {
    return this._client.getAPIList(
      path`/api/v1/datasets/${datasetID}/versions`,
      OffsetPaginationTopLevelArray<DatasetsAPI.DatasetVersion>,
      { query, ...options },
    );
  }

  /**
   * Get diff between two dataset versions.
   */
  retrieveDiff(
    datasetID: string,
    query: VersionRetrieveDiffParams,
    options?: RequestOptions,
  ): APIPromise<VersionRetrieveDiffResponse> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/versions/diff`, { query, ...options });
  }
}

/**
 * Dataset diff schema.
 */
export interface VersionRetrieveDiffResponse {
  examples_added: Array<string>;

  examples_modified: Array<string>;

  examples_removed: Array<string>;
}

export interface VersionListParams extends OffsetPaginationTopLevelArrayParams {
  example?: string | null;

  search?: string | null;
}

export interface VersionRetrieveDiffParams {
  from_version: (string & {}) | string;

  to_version: (string & {}) | string;
}

export declare namespace Versions {
  export {
    type VersionRetrieveDiffResponse as VersionRetrieveDiffResponse,
    type VersionListParams as VersionListParams,
    type VersionRetrieveDiffParams as VersionRetrieveDiffParams,
  };
}

export { type DatasetVersionsOffsetPaginationTopLevelArray };
