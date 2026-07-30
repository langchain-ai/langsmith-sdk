// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as AnnotationQueuesAPI from './annotation-queues.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Runs extends APIResource {
  /**
   * Add Runs To Annotation Queue
   */
  create(queueID: string, params: RunCreateParams, options?: RequestOptions): APIPromise<RunCreateResponse> {
    const { body, extend_trace_retention } = params;
    return this._client.post(path`/api/v1/annotation-queues/${queueID}/runs`, {
      query: { extend_trace_retention },
      body: body,
      ...options,
    });
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
   * Add Runs To Annotation Queue By Key
   */
  createByKey(
    queueID: string,
    params: RunCreateByKeyParams,
    options?: RequestOptions,
  ): APIPromise<RunCreateByKeyResponse> {
    const { body, extend_trace_retention } = params;
    return this._client.post(path`/api/v1/annotation-queues/${queueID}/runs/by-key`, {
      query: { extend_trace_retention },
      body: body,
      ...options,
    });
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

export type RunCreateByKeyResponse = Array<RunCreateByKeyResponse.RunCreateByKeyResponseItem>;

export namespace RunCreateByKeyResponse {
  export interface RunCreateByKeyResponseItem {
    id: string;

    queue_id: string;

    run_id: string;

    added_at?: string;

    last_reviewed_time?: string | null;

    source_proposed_example_id?: string | null;
  }
}

export type RunDeleteAllResponse = unknown;

export type RunDeleteQueueResponse = unknown;

export type RunCreateParams =
  | RunCreateParams.RunsUuidArray
  | RunCreateParams.RunsAnnotationQueueRunAddSchemaArray
  | RunCreateParams.Variant2;

export declare namespace RunCreateParams {
  export interface RunsUuidArray {
    /**
     * Body param
     */
    body: Array<string>;

    /**
     * Query param
     */
    extend_trace_retention?: boolean;
  }

  export interface RunsAnnotationQueueRunAddSchemaArray {
    /**
     * Body param
     */
    body: Array<RunsAnnotationQueueRunAddSchemaArray.Body>;

    /**
     * Query param
     */
    extend_trace_retention?: boolean;
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
    /**
     * Body param
     */
    body: Array<Variant2.Body>;

    /**
     * Query param
     */
    extend_trace_retention?: boolean;
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

export interface RunCreateByKeyParams {
  /**
   * Body param
   */
  body: Array<RunCreateByKeyParams.Body>;

  /**
   * Query param
   */
  extend_trace_retention?: boolean;
}

export namespace RunCreateByKeyParams {
  /**
   * Add run to AQ by SmithDB key. is_root derived server-side (LSAQ-141).
   */
  export interface Body {
    run_id: string;

    session_id: string;

    start_time: string;

    source_proposed_example_id?: string | null;
  }
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
    type RunCreateByKeyResponse as RunCreateByKeyResponse,
    type RunDeleteAllResponse as RunDeleteAllResponse,
    type RunDeleteQueueResponse as RunDeleteQueueResponse,
    type RunCreateParams as RunCreateParams,
    type RunUpdateParams as RunUpdateParams,
    type RunListParams as RunListParams,
    type RunCreateByKeyParams as RunCreateByKeyParams,
    type RunDeleteAllParams as RunDeleteAllParams,
    type RunDeleteQueueParams as RunDeleteQueueParams,
  };
}
