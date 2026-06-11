// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as ComparativeAPI from '../datasets/comparative';
import * as DatasetsAPI from '../datasets/datasets';
import * as FeedbackAPI from '../feedback/feedback';
import { FeedbackSchemasOffsetPaginationTopLevelArray } from '../feedback/feedback';
import * as SessionsAPI from '../sessions/sessions';
import { TracerSessionsOffsetPaginationTopLevelArray } from '../sessions/sessions';
import { APIPromise } from '../../core/api-promise';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Datasets extends APIResource {
  /**
   * Get dataset by ids or the shared dataset if not specifed.
   */
  list(
    shareToken: string,
    query: DatasetListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<DatasetListResponse> {
    return this._client.get(path`/api/v1/public/${shareToken}/datasets`, { query, ...options });
  }

  /**
   * Get all comparative experiments for a given dataset.
   */
  listComparative(
    shareToken: string,
    query: DatasetListComparativeParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<
    DatasetListComparativeResponsesOffsetPaginationTopLevelArray,
    DatasetListComparativeResponse
  > {
    return this._client.getAPIList(
      path`/api/v1/public/${shareToken}/datasets/comparative`,
      OffsetPaginationTopLevelArray<DatasetListComparativeResponse>,
      { query, ...options },
    );
  }

  /**
   * Get feedback for runs in projects run over a dataset that has been shared.
   */
  listFeedback(
    shareToken: string,
    query: DatasetListFeedbackParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<FeedbackSchemasOffsetPaginationTopLevelArray, FeedbackAPI.FeedbackSchema> {
    return this._client.getAPIList(
      path`/api/v1/public/${shareToken}/datasets/feedback`,
      OffsetPaginationTopLevelArray<FeedbackAPI.FeedbackSchema>,
      { query, ...options },
    );
  }

  /**
   * Get projects run on a dataset that has been shared.
   */
  listSessions(
    shareToken: string,
    params: DatasetListSessionsParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<TracerSessionsOffsetPaginationTopLevelArray, SessionsAPI.TracerSession> {
    const { accept, ...query } = params ?? {};
    return this._client.getAPIList(
      path`/api/v1/public/${shareToken}/datasets/sessions`,
      OffsetPaginationTopLevelArray<SessionsAPI.TracerSession>,
      {
        query,
        ...options,
        headers: buildHeaders([{ ...(accept != null ? { accept: accept } : undefined) }, options?.headers]),
      },
    );
  }

  /**
   * Get sessions from multiple datasets using share tokens.
   */
  retrieveSessionsBulk(
    query: DatasetRetrieveSessionsBulkParams,
    options?: RequestOptions,
  ): APIPromise<DatasetRetrieveSessionsBulkResponse> {
    return this._client.get('/api/v1/public/datasets/sessions-bulk', { query, ...options });
  }
}

export type DatasetListComparativeResponsesOffsetPaginationTopLevelArray =
  OffsetPaginationTopLevelArray<DatasetListComparativeResponse>;

/**
 * Public schema for datasets.
 *
 * Doesn't currently include session counts/stats since public test project sharing
 * is not yet shipped
 */
export interface DatasetListResponse {
  id: string;

  example_count: number;

  name: string;

  created_at?: string;

  /**
   * Enum for dataset data types.
   */
  data_type?: DatasetsAPI.DataType | null;

  description?: string | null;

  externally_managed?: boolean | null;

  inputs_schema_definition?: { [key: string]: unknown } | null;

  outputs_schema_definition?: { [key: string]: unknown } | null;

  transformations?: Array<DatasetsAPI.DatasetTransformation> | null;
}

/**
 * Publicly-shared ComparativeExperiment schema.
 */
export interface DatasetListComparativeResponse {
  id: string;

  created_at: string;

  experiments_info: Array<ComparativeAPI.SimpleExperimentInfo>;

  modified_at: string;

  description?: string | null;

  extra?: { [key: string]: unknown } | null;

  feedback_stats?: { [key: string]: unknown } | null;

  name?: string | null;
}

export type DatasetRetrieveSessionsBulkResponse = Array<SessionsAPI.TracerSession>;

export interface DatasetListParams {
  limit?: number;

  offset?: number;

  /**
   * Enum for available dataset columns to sort by.
   */
  sort_by?: DatasetsAPI.SortByDatasetColumn;

  sort_by_desc?: boolean;
}

export interface DatasetListComparativeParams extends OffsetPaginationTopLevelArrayParams {
  name?: string | null;

  name_contains?: string | null;

  /**
   * Enum for available comparative experiment columns to sort by.
   */
  sort_by?: ComparativeAPI.SortByComparativeExperimentColumn;

  sort_by_desc?: boolean;
}

export interface DatasetListFeedbackParams extends OffsetPaginationTopLevelArrayParams {
  has_comment?: boolean | null;

  has_score?: boolean | null;

  key?: Array<string> | null;

  /**
   * Enum for feedback levels.
   */
  level?: FeedbackAPI.FeedbackLevel | null;

  run?: Array<string> | null;

  session?: Array<string> | null;

  source?: Array<FeedbackAPI.SourceType> | null;

  user?: Array<string> | null;
}

export interface DatasetListSessionsParams extends OffsetPaginationTopLevelArrayParams {
  /**
   * Query param
   */
  id?: Array<string> | null;

  /**
   * Query param
   */
  dataset_version?: string | null;

  /**
   * Query param
   */
  facets?: boolean;

  /**
   * Query param
   */
  name?: string | null;

  /**
   * Query param
   */
  name_contains?: string | null;

  /**
   * Query param
   */
  sort_by?: SessionsAPI.SessionSortableColumns;

  /**
   * Query param
   */
  sort_by_desc?: boolean;

  /**
   * Query param
   */
  sort_by_feedback_key?: string | null;

  /**
   * Header param
   */
  accept?: string;
}

export interface DatasetRetrieveSessionsBulkParams {
  share_tokens: Array<string>;
}

export declare namespace Datasets {
  export {
    type DatasetListResponse as DatasetListResponse,
    type DatasetListComparativeResponse as DatasetListComparativeResponse,
    type DatasetRetrieveSessionsBulkResponse as DatasetRetrieveSessionsBulkResponse,
    type DatasetListComparativeResponsesOffsetPaginationTopLevelArray as DatasetListComparativeResponsesOffsetPaginationTopLevelArray,
    type DatasetListParams as DatasetListParams,
    type DatasetListComparativeParams as DatasetListComparativeParams,
    type DatasetListFeedbackParams as DatasetListFeedbackParams,
    type DatasetListSessionsParams as DatasetListSessionsParams,
    type DatasetRetrieveSessionsBulkParams as DatasetRetrieveSessionsBulkParams,
  };
}

export {
  type FeedbackSchemasOffsetPaginationTopLevelArray,
  type TracerSessionsOffsetPaginationTopLevelArray,
};
