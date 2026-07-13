// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import {
  ItemsCursorGetPagination,
  type ItemsCursorGetPaginationParams,
  ItemsCursorPostPagination,
  type ItemsCursorPostPaginationParams,
  PagePromise,
} from '../core/pagination.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class Threads extends APIResource {
  /**
   * **Alpha:** The request and response contract may change; Retrieve all traces
   * belonging to a specific thread within a project.
   *
   * @example
   * ```ts
   * // Automatically fetches more pages as needed.
   * for await (const threadTraceListItem of client.threads.listTraces(
   *   'thread_id',
   *   { project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e' },
   * )) {
   *   // ...
   * }
   * ```
   */
  listTraces(
    threadID: string,
    query: ThreadListTracesParams,
    options?: RequestOptions,
  ): PagePromise<ThreadTraceListItemsItemsCursorGetPagination, ThreadTraceListItem> {
    return this._client.getAPIList(
      path`/v2/threads/${threadID}/traces`,
      ItemsCursorGetPagination<ThreadTraceListItem>,
      { query, ...options },
    );
  }

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

  /**
   * **Alpha:** The request and response contract may change; Compute aggregate stats
   * for a single thread (turn count, latency percentiles, token/cost sums, and
   * detail breakdowns) within a project.
   *
   * @example
   * ```ts
   * const response = await client.threads.stats('thread_id', {
   *   selects: ['TURNS'],
   *   session_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   * });
   * ```
   */
  stats(
    threadID: string,
    query: ThreadStatsParams,
    options?: RequestOptions,
  ): APIPromise<ThreadStatsResponse> {
    return this._client.get(path`/v2/threads/${threadID}/stats`, { query, ...options });
  }
}

export type ThreadTraceListItemsItemsCursorGetPagination = ItemsCursorGetPagination<ThreadTraceListItem>;

export type ThreadListItemsItemsCursorPostPagination = ItemsCursorPostPagination<ThreadListItem>;

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

export interface ThreadStatsResponse {
  /**
   * `completion_cost` is the sum of per-trace completion costs across the thread, in
   * USD. Populated when `COMPLETION_COST` is selected.
   */
  completion_cost?: number;

  /**
   * `completion_cost_details` is the per-sub-category sum of completion cost details
   * across the thread. Populated when `COMPLETION_COST_DETAILS` is selected.
   */
  completion_cost_details?: ThreadStatsResponse.CompletionCostDetails;

  /**
   * `completion_token_details` is the per-sub-category sum of completion token
   * details across the thread. Populated when `COMPLETION_TOKEN_DETAILS` is
   * selected.
   */
  completion_token_details?: ThreadStatsResponse.CompletionTokenDetails;

  /**
   * `completion_tokens` is the sum of per-trace completion token counts across the
   * thread. Populated when `COMPLETION_TOKENS` is selected.
   */
  completion_tokens?: number;

  /**
   * `feedback_stats` aggregates run-level feedback across the thread's traces, keyed
   * by feedback key. Populated when `FEEDBACK_STATS` is selected.
   */
  feedback_stats?: { [key: string]: ThreadStatsResponse.FeedbackStats };

  /**
   * `first_start_time` is the earliest trace start time in the thread (RFC3339).
   * Populated when `FIRST_START_TIME` is selected.
   */
  first_start_time?: string;

  /**
   * `last_end_time` is the latest trace end time in the thread (RFC3339). Populated
   * when `LAST_END_TIME` is selected.
   */
  last_end_time?: string;

  /**
   * `last_start_time` is the latest trace start time in the thread (RFC3339).
   * Populated when `LAST_START_TIME` is selected.
   */
  last_start_time?: string;

  /**
   * `latency_p50_seconds` is the approximate p50 of trace latency across the thread,
   * in seconds. Populated when `LATENCY_P50` is selected.
   */
  latency_p50_seconds?: number;

  /**
   * `latency_p99_seconds` is the approximate p99 of trace latency across the thread,
   * in seconds. Populated when `LATENCY_P99` is selected.
   */
  latency_p99_seconds?: number;

  /**
   * `prompt_cost` is the sum of per-trace prompt costs across the thread, in USD.
   * Populated when `PROMPT_COST` is selected.
   */
  prompt_cost?: number;

  /**
   * `prompt_cost_details` is the per-sub-category sum of prompt cost details across
   * the thread. Populated when `PROMPT_COST_DETAILS` is selected.
   */
  prompt_cost_details?: ThreadStatsResponse.PromptCostDetails;

  /**
   * `prompt_token_details` is the per-sub-category sum of prompt token details
   * across the thread. Populated when `PROMPT_TOKEN_DETAILS` is selected.
   */
  prompt_token_details?: ThreadStatsResponse.PromptTokenDetails;

  /**
   * `prompt_tokens` is the sum of per-trace prompt token counts across the thread.
   * Populated when `PROMPT_TOKENS` is selected.
   */
  prompt_tokens?: number;

  /**
   * `total_cost` is the sum of per-trace total costs across the thread, in USD.
   * Populated when `TOTAL_COST` is selected.
   */
  total_cost?: number;

  /**
   * `total_tokens` is the sum of per-trace total token counts across the thread.
   * Populated when `TOTAL_TOKENS` is selected.
   */
  total_tokens?: number;

  /**
   * `turns` is the number of distinct traces (turns) in the thread. Populated when
   * `TURNS` is selected.
   */
  turns?: number;
}

export namespace ThreadStatsResponse {
  /**
   * `completion_cost_details` is the per-sub-category sum of completion cost details
   * across the thread. Populated when `COMPLETION_COST_DETAILS` is selected.
   */
  export interface CompletionCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `completion_token_details` is the per-sub-category sum of completion token
   * details across the thread. Populated when `COMPLETION_TOKEN_DETAILS` is
   * selected.
   */
  export interface CompletionTokenDetails {
    /**
     * `raw` maps each category name to its completion-token count.
     */
    raw?: { [key: string]: number };
  }

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

  /**
   * `prompt_cost_details` is the per-sub-category sum of prompt cost details across
   * the thread. Populated when `PROMPT_COST_DETAILS` is selected.
   */
  export interface PromptCostDetails {
    /**
     * `raw` maps each category name to its estimated USD cost.
     */
    raw?: { [key: string]: number };
  }

  /**
   * `prompt_token_details` is the per-sub-category sum of prompt token details
   * across the thread. Populated when `PROMPT_TOKEN_DETAILS` is selected.
   */
  export interface PromptTokenDetails {
    /**
     * `raw` maps each category name to its prompt-token count.
     */
    raw?: { [key: string]: number };
  }
}

export interface ThreadListTracesParams extends ItemsCursorGetPaginationParams {
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
   * `max_start_time` is the exclusive upper bound on thread activity (RFC3339
   * date-time). Defaults to now (UTC) when omitted.
   */
  max_start_time?: string;

  /**
   * `min_start_time` is the inclusive lower bound on thread activity (RFC3339
   * date-time). Defaults to 1 day before now (UTC) when omitted.
   */
  min_start_time?: string;

  /**
   * `project_id` is the tracing project UUID.
   */
  project_id?: string;
}

export interface ThreadStatsParams {
  /**
   * `selects` lists which aggregate stats to compute and return (repeatable query
   * parameter). At least one value is required. Accepts any value of
   * `SingleThreadStatsSelectField`.
   */
  selects: Array<
    | 'TURNS'
    | 'FIRST_START_TIME'
    | 'LAST_START_TIME'
    | 'LAST_END_TIME'
    | 'LATENCY_P50'
    | 'LATENCY_P99'
    | 'PROMPT_TOKENS'
    | 'PROMPT_COST'
    | 'COMPLETION_TOKENS'
    | 'COMPLETION_COST'
    | 'TOTAL_TOKENS'
    | 'TOTAL_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'FEEDBACK_STATS'
  >;

  /**
   * `session_id` is the tracing project (session) UUID (required).
   */
  session_id: string;

  /**
   * `filter` narrows which of the thread's traces are aggregated, using a LangSmith
   * filter expression. For example: lt(start_time, "2025-01-01T00:00:00Z") or
   * eq(trace_id, "0190a1b2-c3d4-7ef0-a5b6-6ea3a82e9328"). See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;
}

export declare namespace Threads {
  export {
    type ThreadListItem as ThreadListItem,
    type ThreadTraceListItem as ThreadTraceListItem,
    type ThreadStatsResponse as ThreadStatsResponse,
    type ThreadTraceListItemsItemsCursorGetPagination as ThreadTraceListItemsItemsCursorGetPagination,
    type ThreadListItemsItemsCursorPostPagination as ThreadListItemsItemsCursorPostPagination,
    type ThreadListTracesParams as ThreadListTracesParams,
    type ThreadQueryParams as ThreadQueryParams,
    type ThreadStatsParams as ThreadStatsParams,
  };
}
