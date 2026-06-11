// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import * as AnnotationQueuesAPI from './annotation-queues';
import { APIPromise } from '../../core/api-promise';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Runs extends APIResource {
  /**
   * Add Runs To Annotation Queue
   */
  create(queueID: string, params: RunCreateParams, options?: RequestOptions): APIPromise<RunCreateResponse> {
    const { body } = params;
    return this._client.post(path`/api/v1/annotation-queues/${queueID}/runs`, { body: body, ...options });
  }

  /**
   * Update Run In Annotation Queue
   */
  update(queueRunID: string, params: RunUpdateParams, options?: RequestOptions): APIPromise<unknown> {
    const { queue_id, ...body } = params;
    return this._client.patch(path`/api/v1/annotation-queues/${queue_id}/runs/${queueRunID}`, {
      body,
      ...options,
    });
  }

  /**
   * Get Runs From Annotation Queue
   */
  list(
    queueID: string,
    query: RunListParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<RunListResponse> {
    return this._client.get(path`/api/v1/annotation-queues/${queueID}/runs`, { query, ...options });
  }

  /**
   * Delete Runs From Annotation Queue
   */
  deleteAll(queueID: string, body: RunDeleteAllParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post(path`/api/v1/annotation-queues/${queueID}/runs/delete`, { body, ...options });
  }

  /**
   * Delete Run From Annotation Queue
   */
  deleteQueue(
    queueRunID: string,
    params: RunDeleteQueueParams,
    options?: RequestOptions,
  ): APIPromise<unknown> {
    const { queue_id } = params;
    return this._client.delete(path`/api/v1/annotation-queues/${queue_id}/runs/${queueRunID}`, options);
  }
}

export type RunCreateResponse = Array<RunCreateResponse.RunCreateResponseItem>;

export namespace RunCreateResponse {
  export interface RunCreateResponseItem {
    id: string;

    queue_id: string;

    run_id: string;

    added_at?: string;

    last_reviewed_time?: string | null;

    source_proposed_example_id?: string | null;
  }
}

export type RunUpdateResponse = unknown;

export type RunListResponse = Array<AnnotationQueuesAPI.RunSchemaWithAnnotationQueueInfo>;

export type RunDeleteAllResponse = unknown;

export type RunDeleteQueueResponse = unknown;

export type RunCreateParams =
  | RunCreateParams.RunsUuidArray
  | RunCreateParams.RunsAnnotationQueueRunAddSchemaArray
  | RunCreateParams.Variant2;

export declare namespace RunCreateParams {
  export interface RunsUuidArray {
    body: Array<string>;
  }

  export interface RunsAnnotationQueueRunAddSchemaArray {
    body: Array<RunsAnnotationQueueRunAddSchemaArray.Body>;
  }

  export namespace RunsAnnotationQueueRunAddSchemaArray {
    /**
     * Add a single run to AQ (CH path) with an optional back-pointer to the
     * issues-agent proposal that seeded this add. Use when bulk-adding runs that come
     * from different proposals — each row carries its own source_proposed_example_id.
     * For unrelated bulk adds, prefer plain List[UUID] on the same endpoint.
     */
    export interface Body {
      run_id: string;

      source_proposed_example_id?: string | null;
    }
  }

  export interface Variant2 {
    body: Array<Variant2.Body>;
  }

  export namespace Variant2 {
    /**
     * Deprecated: use plain UUID list or AddRunToQueueByKeyRequest instead.
     */
    export interface Body {
      /**
       * @deprecated
       */
      run_id: string;

      /**
       * @deprecated
       */
      parent_run_id?: string | null;

      /**
       * @deprecated
       */
      session_id?: string | null;

      /**
       * @deprecated
       */
      start_time?: string | null;

      /**
       * @deprecated
       */
      trace_id?: string | null;

      /**
       * @deprecated
       */
      trace_tier?: 'longlived' | 'shortlived' | null;
    }
  }
}

export interface RunUpdateParams {
  /**
   * Path param
   */
  queue_id: string;

  /**
   * Body param
   */
  added_at?: string | null;

  /**
   * Body param
   */
  last_reviewed_time?: string | null;
}

export interface RunListParams {
  archived?: boolean | null;

  include_stats?: boolean | null;

  limit?: number;

  offset?: number;

  status?: 'needs_my_review' | 'needs_others_review' | 'completed' | null;
}

export interface RunDeleteAllParams {
  delete_all?: boolean;

  exclude_run_ids?: Array<string> | null;

  run_ids?: Array<string> | null;
}

export interface RunDeleteQueueParams {
  queue_id: string;
}

export declare namespace Runs {
  export {
    type RunCreateResponse as RunCreateResponse,
    type RunUpdateResponse as RunUpdateResponse,
    type RunListResponse as RunListResponse,
    type RunDeleteAllResponse as RunDeleteAllResponse,
    type RunDeleteQueueResponse as RunDeleteQueueResponse,
    type RunCreateParams as RunCreateParams,
    type RunUpdateParams as RunUpdateParams,
    type RunListParams as RunListParams,
    type RunDeleteAllParams as RunDeleteAllParams,
    type RunDeleteQueueParams as RunDeleteQueueParams,
  };
}
