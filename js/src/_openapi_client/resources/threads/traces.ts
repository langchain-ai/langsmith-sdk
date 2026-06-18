// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ThreadsAPI from './threads.js';
import { ThreadTraceListItemsItemsCursorGetPagination } from './threads.js';
import {
  ItemsCursorGetPagination,
  type ItemsCursorGetPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Traces extends APIResource {
  /**
   * **Alpha:** The request and response contract may change; Retrieve all traces
   * belonging to a specific thread within a project.
   *
   * @example
   * ```ts
   * // Automatically fetches more pages as needed.
   * for await (const threadTraceListItem of client.threads.traces.list(
   *   'thread_id',
   *   { project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e' },
   * )) {
   *   // ...
   * }
   * ```
   */
  list(
    threadID: string,
    query: TraceListParams,
    options?: RequestOptions,
  ): PagePromise<ThreadTraceListItemsItemsCursorGetPagination, ThreadsAPI.ThreadTraceListItem> {
    return this._client.getAPIList(
      path`/v2/threads/${threadID}/traces`,
      ItemsCursorGetPagination<ThreadsAPI.ThreadTraceListItem>,
      { query, ...options },
    );
  }
}

export interface TraceListParams extends ItemsCursorGetPaginationParams {
  /**
   * `project_id` is the tracing project UUID (required).
   */
  project_id: string;

  /**
   * `filter` narrows which traces are returned for this thread, using a LangSmith
   * filter expression evaluated against each root trace run. For example: eq(status,
   * "success") or has(tags, "production"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * `selects` lists which properties to include on each returned trace (repeatable
   * query parameter). Accepts any value of the `ThreadTraceSelectField` enum.
   * Properties not listed are omitted from each trace object; `trace_id` is always
   * returned.
   */
  selects?: Array<
    | 'THREAD_ID'
    | 'TRACE_ID'
    | 'OP'
    | 'PROMPT_TOKENS'
    | 'COMPLETION_TOKENS'
    | 'TOTAL_TOKENS'
    | 'START_TIME'
    | 'END_TIME'
    | 'LATENCY'
    | 'FIRST_TOKEN_TIME'
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS_PREVIEW'
    | 'PROMPT_COST'
    | 'COMPLETION_COST'
    | 'TOTAL_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'NAME'
    | 'ERROR_PREVIEW'
  >;
}

export declare namespace Traces {
  export { type TraceListParams as TraceListParams };
}

export { type ThreadTraceListItemsItemsCursorGetPagination };
