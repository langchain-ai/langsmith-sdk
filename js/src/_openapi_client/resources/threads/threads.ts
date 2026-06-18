// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as TracesAPI from './traces.js';
import { TraceListParams, Traces } from './traces.js';
import {
  ItemsCursorGetPagination,
  ItemsCursorPostPagination,
  type ItemsCursorPostPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';

export class Threads extends APIResource {
  traces: TracesAPI.Traces = new TracesAPI.Traces(this._client);

  /**
   * **Alpha:** The request and response contract may change; Query threads within a
   * project (session), with cursor-based pagination. Returns threads matching the
   * given time range and optional filter.
   *
   * @example
   * ```ts
   * // Automatically fetches more pages as needed.
   * for await (const threadListItem of client.threads.query()) {
   *   // ...
   * }
   * ```
   */
  query(
    body: ThreadQueryParams,
    options?: RequestOptions,
  ): PagePromise<ThreadListItemsItemsCursorPostPagination, ThreadListItem> {
    return this._client.getAPIList('/v2/threads/query', ItemsCursorPostPagination<ThreadListItem>, {
      body,
      method: 'post',
      ...options,
    });
  }
}

export type ThreadListItemsItemsCursorPostPagination = ItemsCursorPostPagination<ThreadListItem>;

export type ThreadTraceListItemsItemsCursorGetPagination = ItemsCursorGetPagination<ThreadTraceListItem>;

export interface QueryThreadsRequestBody {
  /**
   * `cursor` is the opaque string from a previous response's `next_cursor`. Omit on
   * the first request; pass the returned cursor to fetch the next page.
   */
  cursor?: string;

  /**
   * `filter` narrows which threads are returned, using a LangSmith filter expression
   * evaluated against each thread's root run. For example: has(tags, "production")
   * or eq(status, "error"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * `max_start_time` is the inclusive upper bound on thread activity (RFC3339
   * date-time).
   */
  max_start_time?: string;

  /**
   * `min_start_time` is the inclusive lower bound on thread activity (RFC3339
   * date-time).
   */
  min_start_time?: string;

  /**
   * `page_size` is the maximum number of threads to return in this response.
   * Defaults to 20 when omitted; must be between 1 and 100 inclusive when set. The
   * response may contain fewer threads than `page_size` even when `next_cursor` is
   * present.
   */
  page_size?: number;

  /**
   * `project_id` is the tracing project UUID.
   */
  project_id?: string;
}

export interface ThreadListItem {
  /**
   * `count` is how many root traces (conversation turns) fall in this thread for the
   * query time range.
   */
  count?: number;

  /**
   * `feedback_stats` is the aggregated feedback across traces in the thread, keyed
   * by feedback key; shape matches `feedback_stats` on a single run.
   */
  feedback_stats?: { [key: string]: ThreadListItem.FeedbackStats };

  /**
   * `first_inputs` is a truncated preview of inputs from the earliest trace in the
   * thread for the query window.
   */
  first_inputs?: string;

  /**
   * `first_trace_id` is the root trace UUID for the chronologically first trace in
   * the query time window.
   */
  first_trace_id?: string;

  /**
   * `last_error` is a short error summary from the most recent failing trace in the
   * thread. Absent when there is no error in the window.
   */
  last_error?: string;

  /**
   * `last_outputs` is a truncated preview of outputs from the latest trace in the
   * thread for the query window.
   */
  last_outputs?: string;

  /**
   * `last_trace_id` is the root trace UUID for the chronologically last trace in the
   * query time window.
   */
  last_trace_id?: string;

  /**
   * `latency_p50` is the approximate median end-to-end latency of traces in the
   * thread, in seconds.
   */
  latency_p50?: number;

  /**
   * `latency_p99` is the approximate 99th percentile end-to-end latency of traces in
   * the thread, in seconds.
   */
  latency_p99?: number;

  /**
   * `max_start_time` is the latest trace start time in the thread (RFC3339
   * date-time).
   */
  max_start_time?: string;

  /**
   * `min_start_time` is the earliest trace start time in the thread (RFC3339
   * date-time).
   */
  min_start_time?: string;

  /**
   * `num_errored_turns` is the count of root traces in the thread (within the query
   * window) whose status was an error.
   */
  num_errored_turns?: number;

  /**
   * `start_time` is a reference start time for this row (RFC3339 date-time), such as
   * for sorting.
   */
  start_time?: string;

  /**
   * `thread_id` identifies this conversation thread within the project from the
   * request body `project_id`.
   */
  thread_id?: string;

  /**
   * `total_cost` is the sum of estimated USD cost across those traces.
   */
  total_cost?: number;

  /**
   * `total_cost_details` sums per-category estimated USD cost across traces in the
   * thread. Keys mirror `total_token_details`.
   *
   * Example: `{"cache_read": 0.012, "reasoning": 0.008}`.
   */
  total_cost_details?: { [key: string]: number };

  /**
   * `total_token_details` sums per-category token counts across traces in the
   * thread. Keys are model-specific category names (for example `cache_read`,
   * `cache_write`, `reasoning`, `audio`).
   *
   * Example: `{"cache_read": 400, "reasoning": 120}`.
   */
  total_token_details?: { [key: string]: number };

  /**
   * `total_tokens` is the sum of token usage across those traces.
   */
  total_tokens?: number;

  /**
   * `trace_id` is a representative root trace UUID when the summary includes one,
   * for example for deep links.
   */
  trace_id?: string;
}

export namespace ThreadListItem {
  export interface FeedbackStats {
    /**
     * `avg` is the arithmetic mean of numeric feedback scores for this key on the run,
     * or `null` when no numeric score has been recorded (for example purely
     * categorical feedback).
     */
    avg?: number;

    /**
     * `comments` is a sample of human-readable comments attached to feedback points
     * for this key, in no particular order. May be empty; is not exhaustive when many
     * comments exist.
     */
    comments?: Array<string>;

    /**
     * `contains_thread_feedback` is true when at least one feedback point for this key
     * was submitted at the thread level (rather than at an individual run). Always
     * false on responses that already describe a single run in isolation.
     */
    contains_thread_feedback?: boolean;

    /**
     * `errors` is the number of feedback points recorded as errors rather than
     * successful scores (for example an automated evaluator that raised an exception).
     * Defaults to 0 when no errors occurred.
     */
    errors?: number;

    /**
     * `max` is the largest numeric feedback score recorded for this key on the run, or
     * `null` when no numeric score has been recorded.
     */
    max?: number;

    /**
     * `min` is the smallest numeric feedback score recorded for this key on the run,
     * or `null` when no numeric score has been recorded.
     */
    min?: number;

    /**
     * `n` is the number of feedback points recorded for this key on the run. For
     * numeric feedback this is the sample size behind `avg`, `min`, `max`, and
     * `stdev`; for categorical feedback it is the sum of the `values` counts.
     */
    n?: number;

    /**
     * `sources` is a sample of feedback sources for this key. Each entry is either a
     * plain string identifier (for example `"api"`, `"app"`, `"model"`) or a JSON
     * object describing a synthetic source (for example
     * `{"type": "__ls_composite_feedback"}` for a computed aggregate). Clients must
     * tolerate both shapes.
     */
    sources?: Array<unknown>;

    /**
     * `stdev` is the sample standard deviation of numeric feedback scores for this key
     * on the run, or `null` when it cannot be computed (for example fewer than two
     * numeric scores, or purely categorical feedback).
     */
    stdev?: number;

    /**
     * `values` is the distribution of categorical feedback labels for this key,
     * mapping each label to its occurrence count. Empty (`{}`) for purely numeric
     * feedback.
     */
    values?: { [key: string]: number };
  }
}

export interface ThreadTraceListItem {
  /**
   * `completion_cost` is the estimated USD cost for the completion. Omitted unless
   * included in `selects`.
   */
  completion_cost?: number;

  /**
   * `completion_cost_details` is the USD cost breakdown for completion-side
   * categories; per-category values are under `raw`. Omitted unless included in
   * `selects`.
   */
  completion_cost_details?: ThreadTraceListItem.CompletionCostDetails;

  /**
   * `completion_token_details` is the completion-side token breakdown by category;
   * per-category counts are under `raw`. Omitted unless included in `selects`.
   */
  completion_token_details?: ThreadTraceListItem.CompletionTokenDetails;

  /**
   * `completion_tokens` is the completion-side token count. Omitted unless included
   * in `selects`.
   */
  completion_tokens?: number;

  /**
   * `end_time` is when the root run ended (RFC3339 date-time). JSON null if the run
   * is still in progress. Omitted unless included in `selects`.
   */
  end_time?: string;

  /**
   * `error_preview` is a short error summary when the run failed. Omitted unless
   * included in `selects`.
   */
  error_preview?: string;

  /**
   * `first_token_time` is when the first output token was produced (RFC3339
   * date-time), for streamed runs when that metadata exists. Omitted unless included
   * in `selects`.
   */
  first_token_time?: string;

  /**
   * `inputs_preview` is a truncated text preview of inputs. Omitted unless included
   * in `selects`.
   */
  inputs_preview?: string;

  /**
   * `latency` is wall-clock duration from start to end in seconds. Omitted unless
   * included in `selects`.
   */
  latency?: number;

  /**
   * `name` is a human-readable label for the root run (for example the model name,
   * function name, or step name chosen when the run was traced). Omitted unless
   * included in `selects`.
   */
  name?: string;

  /**
   * `op` is a numeric code identifying the root run's `run_type` (for example LLM
   * vs. tool vs. chain). Encoded as a number for compatibility with legacy clients;
   * prefer the string `run_type` on `RunResponse` when available. Omitted unless
   * included in `selects`.
   */
  op?: number;

  /**
   * `outputs_preview` is a truncated text preview of outputs. Omitted unless
   * included in `selects`.
   */
  outputs_preview?: string;

  /**
   * `prompt_cost` is the estimated USD cost for the prompt. Omitted unless included
   * in `selects`.
   */
  prompt_cost?: number;

  /**
   * `prompt_cost_details` is the USD cost breakdown for prompt-side categories;
   * per-category values are under `raw`. Omitted unless included in `selects`.
   */
  prompt_cost_details?: ThreadTraceListItem.PromptCostDetails;

  /**
   * `prompt_token_details` is the prompt-side token breakdown by category;
   * per-category counts are under nested `raw`. Omitted unless included in
   * `selects`.
   */
  prompt_token_details?: ThreadTraceListItem.PromptTokenDetails;

  /**
   * `prompt_tokens` is the prompt-side token count. Omitted unless included in
   * `selects`.
   */
  prompt_tokens?: number;

  /**
   * `start_time` is when the trace started (RFC3339 date-time). Omitted unless
   * included in `selects`.
   */
  start_time?: string;

  /**
   * `thread_id` is the conversation thread UUID that contains this trace. Matches
   * the `thread_id` path parameter of the request. Omitted unless included in
   * `selects`.
   */
  thread_id?: string;

  /**
   * `total_cost` is the estimated total USD cost for the root run. Omitted unless
   * included in `selects`.
   */
  total_cost?: number;

  /**
   * `total_tokens` is the total token count (prompt plus completion). Omitted unless
   * included in `selects`.
   */
  total_tokens?: number;

  /**
   * `trace_id` is the UUID of this trace (the root run). Always present.
   */
  trace_id?: string;
}

export namespace ThreadTraceListItem {
  /**
   * `completion_cost_details` is the USD cost breakdown for completion-side
   * categories; per-category values are under `raw`. Omitted unless included in
   * `selects`.
   */
  export interface CompletionCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `completion_token_details` is the completion-side token breakdown by category;
   * per-category counts are under `raw`. Omitted unless included in `selects`.
   */
  export interface CompletionTokenDetails {
    /**
     * `raw` maps each category name to its completion-token count.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `prompt_cost_details` is the USD cost breakdown for prompt-side categories;
   * per-category values are under `raw`. Omitted unless included in `selects`.
   */
  export interface PromptCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `prompt_token_details` is the prompt-side token breakdown by category;
   * per-category counts are under nested `raw`. Omitted unless included in
   * `selects`.
   */
  export interface PromptTokenDetails {
    /**
     * `raw` maps each category name to its prompt-token count.
     */
    raw?: { [key: string]: number };
  }
}

export type ThreadTraceSelectField =
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
  | 'ERROR_PREVIEW';

export interface ThreadQueryParams extends ItemsCursorPostPaginationParams {
  /**
   * `filter` narrows which threads are returned, using a LangSmith filter expression
   * evaluated against each thread's root run. For example: has(tags, "production")
   * or eq(status, "error"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * `max_start_time` is the inclusive upper bound on thread activity (RFC3339
   * date-time).
   */
  max_start_time?: string;

  /**
   * `min_start_time` is the inclusive lower bound on thread activity (RFC3339
   * date-time).
   */
  min_start_time?: string;

  /**
   * `project_id` is the tracing project UUID.
   */
  project_id?: string;
}

Threads.Traces = Traces;

export declare namespace Threads {
  export {
    type QueryThreadsRequestBody as QueryThreadsRequestBody,
    type ThreadListItem as ThreadListItem,
    type ThreadTraceListItem as ThreadTraceListItem,
    type ThreadTraceSelectField as ThreadTraceSelectField,
    type ThreadListItemsItemsCursorPostPagination as ThreadListItemsItemsCursorPostPagination,
    type ThreadQueryParams as ThreadQueryParams,
  };

  export { Traces as Traces, type TraceListParams as TraceListParams };
}
