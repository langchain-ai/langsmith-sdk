// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  ItemsCursorGetPagination,
  type ItemsCursorGetPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Items extends APIResource {
  /**
   * Add RUN or THREAD items to a single annotation queue. RUN items require run_id
   * unless they are created from a suggested example. THREAD items require thread_id
   * and project_id.
   */
  create(
    queueID: string,
    params: ItemCreateParams,
    options?: RequestOptions,
  ): APIPromise<ItemCreateResponse> {
    const { extend_trace_retention, ...body } = params;
    return this._client.post(path`/api/v1/platform/annotation-queues/${queueID}/items`, {
      query: { extend_trace_retention },
      body,
      ...options,
    });
  }

  /**
   * Partially update mutable timestamps (added_at, last_reviewed_time) for a RUN or
   * THREAD annotation queue item. Omit a field, or pass JSON null, to leave it
   * unchanged.
   */
  update(itemID: string, params: ItemUpdateParams, options?: RequestOptions): APIPromise<ItemUpdateResponse> {
    const { queue_id, ...body } = params;
    return this._client.patch(path`/api/v1/platform/annotation-queues/${queue_id}/items/${itemID}`, {
      body,
      ...options,
    });
  }

  /**
   * List RUN and THREAD items in a single annotation queue for one review status
   * section, with opaque cursor pagination. Optional item_type=RUN|THREAD filters
   * the page. direction=backward returns items before the supplied cursor. The
   * response contains item metadata only, not expanded run or thread payloads.
   * status=archived returns items whose queue review requirements have been
   * satisfied, not merely items the caller personally marked completed.
   */
  list(
    queueID: string,
    query: ItemListParams,
    options?: RequestOptions,
  ): PagePromise<ItemListResponsesItemsCursorGetPagination, ItemListResponse> {
    return this._client.getAPIList(
      path`/api/v1/platform/annotation-queues/${queueID}/items`,
      ItemsCursorGetPagination<ItemListResponse>,
      { query, ...options },
    );
  }

  /**
   * Log the caller's reviewer status for a RUN or THREAD annotation queue item. A
   * null status re-shows the item for this reviewer.
   */
  createStatus(
    queueItemID: string,
    body: ItemCreateStatusParams,
    options?: RequestOptions,
  ): APIPromise<ItemCreateStatusResponse> {
    return this._client.post(path`/api/v1/platform/annotation-queues/items/${queueItemID}/status`, {
      body,
      ...options,
    });
  }

  /**
   * Remove RUN or THREAD items from a single annotation queue by item ID.
   */
  deleteAll(
    queueID: string,
    body: ItemDeleteAllParams,
    options?: RequestOptions,
  ): APIPromise<ItemDeleteAllResponse> {
    return this._client.post(path`/api/v1/platform/annotation-queues/${queueID}/items/delete`, {
      body,
      ...options,
    });
  }

  /**
   * Returns the number of annotation queue items for the requested reviewer-specific
   * or archived bucket.
   */
  retrieveCount(
    queueID: string,
    query: ItemRetrieveCountParams,
    options?: RequestOptions,
  ): APIPromise<ItemRetrieveCountResponse> {
    return this._client.get(path`/api/v1/platform/annotation-queues/${queueID}/items/count`, {
      query,
      ...options,
    });
  }

  /**
   * Resolve a RUN or THREAD item to its current review section and zero-based
   * position for deep linking.
   */
  retrievePlacement(
    itemID: string,
    params: ItemRetrievePlacementParams,
    options?: RequestOptions,
  ): APIPromise<ItemRetrievePlacementResponse> {
    const { queue_id } = params;
    return this._client.get(
      path`/api/v1/platform/annotation-queues/${queue_id}/items/${itemID}/placement`,
      options,
    );
  }
}

export type ItemListResponsesItemsCursorGetPagination = ItemsCursorGetPagination<ItemListResponse>;

export interface ItemCreateResponse {
  items?: Array<ItemCreateResponse.Item>;
}

export namespace ItemCreateResponse {
  export interface Item {
    id?: string;

    added_at?: string;

    item_type?: 'RUN' | 'THREAD';

    /**
     * LastReviewedTime is always present on the wire (null until reviewed).
     */
    last_reviewed_time?: string;

    project_id?: string;

    queue_id?: string;

    run_id?: string;

    source_proposed_example_id?: string;

    start_time?: string;

    thread_id?: string;
  }
}

export interface ItemUpdateResponse {
  id?: string;

  added_at?: string;

  item_type?: 'RUN' | 'THREAD';

  /**
   * LastReviewedTime is always present on the wire (null until reviewed).
   */
  last_reviewed_time?: string;

  project_id?: string;

  queue_id?: string;

  run_id?: string;

  source_proposed_example_id?: string;

  start_time?: string;

  thread_id?: string;
}

export interface ItemListResponse {
  id?: string;

  added_at?: string;

  completed_by?: Array<string>;

  effective_added_at?: string;

  item_type?: 'RUN' | 'THREAD';

  /**
   * LastReviewedTime is always present on the wire (null until reviewed).
   */
  last_reviewed_time?: string;

  project_id?: string;

  queue_id?: string;

  reserved_by?: Array<string>;

  run_id?: string;

  source_proposed_example_id?: string;

  start_time?: string;

  thread_id?: string;
}

export interface ItemCreateStatusResponse {
  is_archived?: boolean;

  override_added_at?: string;

  queue_item_id?: string;

  status?: 'viewed' | 'completed';
}

export type ItemDeleteAllResponse = { [key: string]: string };

export interface ItemRetrieveCountResponse {
  count?: number;
}

export interface ItemRetrievePlacementResponse {
  cursor?: string;

  item_type?: 'RUN' | 'THREAD';

  position?: number;

  section?: 'needs_my_review' | 'needs_others_review' | 'archived';
}

export interface ItemCreateParams {
  /**
   * Query param: Extend trace retention for added run items
   */
  extend_trace_retention?: boolean;

  /**
   * Body param
   */
  items?: Array<ItemCreateParams.Item>;
}

export namespace ItemCreateParams {
  export interface Item {
    item_type?: 'RUN' | 'THREAD';

    project_id?: string;

    /**
     * RUN fields
     */
    run_id?: string;

    /**
     * SessionID is an alias for project_id.
     */
    session_id?: string;

    /**
     * SourceProposedExampleID links the queue item to the suggested example it was
     * created from, when applicable.
     */
    source_proposed_example_id?: string;

    start_time?: string;

    thread_id?: string;
  }
}

export interface ItemUpdateParams {
  /**
   * Path param: Annotation queue ID
   */
  queue_id: string;

  /**
   * Body param
   */
  added_at?: string;

  /**
   * Body param
   */
  last_reviewed_time?: string;
}

export interface ItemListParams extends ItemsCursorGetPaginationParams {
  /**
   * Review section: needs_my_review, needs_others_review, or archived
   */
  status: 'needs_my_review' | 'needs_others_review' | 'archived';

  /**
   * Pagination direction. backward requires cursor
   */
  direction?: 'forward' | 'backward';

  /**
   * Filter to RUN or THREAD
   */
  item_type?: 'RUN' | 'THREAD';
}

export interface ItemCreateStatusParams {
  override_added_at?: string;

  status?: 'viewed' | 'completed';
}

export interface ItemDeleteAllParams {
  item_ids?: Array<string>;
}

export interface ItemRetrieveCountParams {
  /**
   * Count bucket: all, needs_my_review, needs_others_review, or archived.
   */
  status: string;

  /**
   * Exclusive upper bound for archived item timestamp
   */
  end_time?: string;

  /**
   * Exclusive lower bound for archived item timestamp
   */
  start_time?: string;
}

export interface ItemRetrievePlacementParams {
  /**
   * Annotation queue ID
   */
  queue_id: string;
}

export declare namespace Items {
  export {
    type ItemCreateResponse as ItemCreateResponse,
    type ItemUpdateResponse as ItemUpdateResponse,
    type ItemListResponse as ItemListResponse,
    type ItemCreateStatusResponse as ItemCreateStatusResponse,
    type ItemDeleteAllResponse as ItemDeleteAllResponse,
    type ItemRetrieveCountResponse as ItemRetrieveCountResponse,
    type ItemRetrievePlacementResponse as ItemRetrievePlacementResponse,
    type ItemListResponsesItemsCursorGetPagination as ItemListResponsesItemsCursorGetPagination,
    type ItemCreateParams as ItemCreateParams,
    type ItemUpdateParams as ItemUpdateParams,
    type ItemListParams as ItemListParams,
    type ItemCreateStatusParams as ItemCreateStatusParams,
    type ItemDeleteAllParams as ItemDeleteAllParams,
    type ItemRetrieveCountParams as ItemRetrieveCountParams,
    type ItemRetrievePlacementParams as ItemRetrievePlacementParams,
  };
}
