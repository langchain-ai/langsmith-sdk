// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Share extends APIResource {
  /**
   * Share a dataset.
   */
  create(
    datasetID: string,
    params: ShareCreateParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<DatasetShareSchema> {
    const { share_projects } = params ?? {};
    return this._client.put(path`/api/v1/datasets/${datasetID}/share`, {
      query: { share_projects },
      ...options,
    });
  }

  /**
   * Get the state of sharing a dataset
   */
  retrieve(datasetID: string, options?: RequestOptions): APIPromise<DatasetShareSchema | null> {
    return this._client.get(path`/api/v1/datasets/${datasetID}/share`, options);
  }

  /**
   * Unshare a dataset.
   */
  deleteAll(datasetID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/datasets/${datasetID}/share`, options);
  }
}

export interface DatasetShareSchema {
  dataset_id: string;

  share_token: string;
}

export type ShareDeleteAllResponse = unknown;

export interface ShareCreateParams {
  share_projects?: boolean;
}

export declare namespace Share {
  export {
    type DatasetShareSchema as DatasetShareSchema,
    type ShareDeleteAllResponse as ShareDeleteAllResponse,
    type ShareCreateParams as ShareCreateParams,
  };
}
