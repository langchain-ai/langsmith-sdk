// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as FeedbackAPI from '../feedback/feedback';
import { FeedbackSchemasOffsetPaginationTopLevelArray } from '../feedback/feedback';
import * as DatasetsAPI from './datasets';
import {
  DatasetListComparativeParams,
  DatasetListComparativeResponse,
  DatasetListComparativeResponsesOffsetPaginationTopLevelArray,
  DatasetListFeedbackParams,
  DatasetListParams,
  DatasetListResponse,
  DatasetListSessionsParams,
  DatasetRetrieveSessionsBulkParams,
  DatasetRetrieveSessionsBulkResponse,
  Datasets,
} from './datasets';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Public extends APIResource {
  datasets: DatasetsAPI.Datasets = new DatasetsAPI.Datasets(this._client);

  /**
   * Read Shared Feedbacks
   */
  retrieveFeedbacks(
    shareToken: string,
    query: PublicRetrieveFeedbacksParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<FeedbackSchemasOffsetPaginationTopLevelArray, FeedbackAPI.FeedbackSchema> {
    return this._client.getAPIList(
      path`/api/v1/public/${shareToken}/feedbacks`,
      OffsetPaginationTopLevelArray<FeedbackAPI.FeedbackSchema>,
      { query, ...options },
    );
  }
}

export interface PublicRetrieveFeedbacksParams extends OffsetPaginationTopLevelArrayParams {
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

Public.Datasets = Datasets;

export declare namespace Public {
  export { type PublicRetrieveFeedbacksParams as PublicRetrieveFeedbacksParams };

  export {
    Datasets as Datasets,
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

export { type FeedbackSchemasOffsetPaginationTopLevelArray };
