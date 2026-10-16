// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import * as RunsAPI from './runs/runs.js';
import { APIPromise } from '../core/api-promise.js';
import {
  ItemsCursorPostPagination,
  type ItemsCursorPostPaginationParams,
  PagePromise,
} from '../core/pagination.js';
import { buildHeaders } from '../internal/headers.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class Traces extends APIResource {
  /**
   * Returns runs for a trace ID within min/max start time. Optional `filter`;
   * repeatable `selects` to select fields to return.
   *
   * Self-hosted deployments require LangSmith `v0.16` or later.
   *
   * @example
   * ```ts
   * const response = await client.traces.listRuns(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   *   { project_id: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e' },
   * );
   * ```
   */
  listRuns(
    traceID: string,
    params: TraceListRunsParams,
    options?: RequestOptions,
  ): APIPromise<TraceListRunsResponse> {
    const { Accept, ...query } = params;
    return this._client.get(path`/api/v2/traces/${traceID}/runs`, {
      query,
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }

  /**
   * Returns a paginated list of traces (root runs) for a single tracing project.
   * Each item carries the trace's root run plus optional trace-wide aggregates
   * (`total_tokens`, `total_cost`, `first_token_time`) under `trace_aggregates`, so
   * clients never have to merge by `trace_id`.
   *
   * Traces are scanned within a `start_time` window: `min_start_time` defaults to 24
   * hours before the request, `max_start_time` defaults to the request time. Set
   * either explicitly to widen or narrow the window.
   *
   * Supports filters (`trace_filter`, `tree_filter`), cursor pagination (`cursor`),
   * and field projection (`selects`).
   *
   * When `ai_search` is set, `Accept: text/event-stream` is required; requests
   * without it return 406. AI search is unavailable on deployments that route
   * queries to the v1 backend and returns 501 there.
   *
   * Self-hosted deployments require LangSmith `v0.16` or later.
   *
   * @example
   * ```ts
   * // Automatically fetches more pages as needed.
   * for await (const trace of client.traces.query()) {
   *   // ...
   * }
   * ```
   */
  query(
    params: TraceQueryParams,
    options?: RequestOptions,
  ): PagePromise<TracesItemsCursorPostPagination, Trace> {
    const { Accept, ...body } = params;
    return this._client.getAPIList('/api/v2/traces/query', ItemsCursorPostPagination<Trace>, {
      body,
      method: 'post',
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }
}

export type TracesItemsCursorPostPagination = ItemsCursorPostPagination<Trace>;

export interface Trace {
  /**
   * `query_metadata` describes why this trace matched the query, including
   * `sem_filter_score` when a semantic filter is used. Returned automatically, or
   * null when unavailable.
   */
  query_metadata?: unknown | null;

  /**
   * `root_run` is the trace's root run. Which properties are populated is controlled
   * by `selects` in the request.
   */
  root_run?: RunsAPI.Run;

  /**
   * `trace_aggregates` carries trace-wide aggregate metrics. Omitted when no
   * aggregate field was selected, or `null` (then later filled) on the streaming
   * wire while the aggregate values are still being computed.
   */
  trace_aggregates?: TraceAggregates;
}

export interface TraceAggregates {
  /**
   * `first_token_time` is when the first output token was produced anywhere in the
   * trace (RFC3339), when recorded.
   */
  first_token_time?: string;

  /**
   * `total_cost` is total estimated USD cost across every run in the trace.
   */
  total_cost?: number;

  /**
   * `total_tokens` is prompt plus completion tokens summed across every run in the
   * trace.
   */
  total_tokens?: number;
}

export interface TraceListRunsResponse {
  /**
   * `items` lists runs in the trace for the requested time window, in `start_time`
   * order.
   */
  items?: Array<RunsAPI.Run>;
}

export interface TraceListRunsParams {
  /**
   * Query param: `project_id` is the UUID of the tracing project that owns the
   * trace.
   */
  project_id: string;

  /**
   * Query param: `filter` narrows which runs within this trace are returned, using a
   * LangSmith filter expression evaluated against each run. For example:
   * `eq(run_type, "llm")` for LLM runs only, or `eq(status, "error")` for failed
   * runs. See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  filter?: string;

  /**
   * Query param: `max_start_time` is the optional inclusive upper bound for run
   * `start_time` (RFC3339 date-time). Required together with `min_start_time`.
   */
  max_start_time?: string;

  /**
   * Query param: `min_start_time` is the optional inclusive lower bound for run
   * `start_time` (RFC3339 date-time). Required together with `max_start_time`.
   */
  min_start_time?: string;

  /**
   * Query param: `selects` lists which properties to include on each returned run
   * (repeatable query parameter). Accepts any value of the `RunSelectField` enum. If
   * omitted, only `id` is returned.
   */
  selects?: Array<
    | 'ID'
    | 'NAME'
    | 'RUN_TYPE'
    | 'STATUS'
    | 'START_TIME'
    | 'END_TIME'
    | 'LATENCY_SECONDS'
    | 'FIRST_TOKEN_TIME'
    | 'ERROR'
    | 'ERROR_PREVIEW'
    | 'EXTRA'
    | 'METADATA'
    | 'EVENTS'
    | 'INPUTS'
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS'
    | 'OUTPUTS_PREVIEW'
    | 'MANIFEST'
    | 'PARENT_RUN_IDS'
    | 'PROJECT_ID'
    | 'TRACE_ID'
    | 'THREAD_ID'
    | 'DOTTED_ORDER'
    | 'IS_ROOT'
    | 'REFERENCE_EXAMPLE_ID'
    | 'REFERENCE_DATASET_ID'
    | 'TOTAL_TOKENS'
    | 'PROMPT_TOKENS'
    | 'COMPLETION_TOKENS'
    | 'TOTAL_COST'
    | 'PROMPT_COST'
    | 'COMPLETION_COST'
    | 'PROMPT_TOKEN_DETAILS'
    | 'COMPLETION_TOKEN_DETAILS'
    | 'PROMPT_COST_DETAILS'
    | 'COMPLETION_COST_DETAILS'
    | 'PRICE_MODEL_ID'
    | 'TAGS'
    | 'APP_PATH'
    | 'ATTACHMENTS'
    | 'THREAD_EVALUATION_TIME'
    | 'IS_IN_DATASET'
    | 'LAST_QUEUED_AT'
    | 'SHARE_URL'
    | 'FEEDBACK_STATS'
    | 'LS_USER_ID'
  >;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export interface TraceQueryParams extends ItemsCursorPostPaginationParams {
  /**
   * Body param: `ai_search` is a plain-language criterion evaluated against the
   * messages from the agent trajectory scoped to the trace. AND-ed with the ordinary
   * filters. Requires semantic filtering enabled for the deployment. Must contain
   * nonempty text of at most 2000 UTF-8 bytes.
   */
  ai_search?: string;

  /**
   * Body param: `max_start_time` is the exclusive upper bound for the root-run start
   * time scan (RFC3339). Defaults to the request time when omitted.
   */
  max_start_time?: string;

  /**
   * Body param: `min_start_time` is the inclusive lower bound for the root-run start
   * time scan (RFC3339). Defaults to 24 hours before the request when omitted.
   */
  min_start_time?: string;

  /**
   * Body param: `project_id` is the UUID of the tracing project that owns the
   * traces. Required.
   */
  project_id?: string;

  /**
   * Body param: `selects` lists which properties to include on each returned trace.
   * Properties listed here are routed to the appropriate sub-object on each item:
   * `total_tokens`, `total_cost`, and `first_token_time` appear under
   * `trace_aggregates`; everything else appears under `root_run`. If omitted, only
   * `id` is returned on `root_run`.
   */
  selects?: Array<RunsAPI.RunSelectField>;

  /**
   * Body param: `trace_filter` narrows results to traces whose root run matches this
   * LangSmith filter expression. This filter targets root runs only —
   * `is_root = true` is implied. See
   * https://docs.langchain.com/langsmith/trace-query-syntax#filter-query-language
   * for syntax.
   */
  trace_filter?: string;

  /**
   * Body param: `trace_ids` is an optional fast-path restriction to a known set of
   * trace UUIDs. Equivalent in result to including each UUID in a `trace_filter`,
   * but more efficient at scale.
   */
  trace_ids?: Array<string>;

  /**
   * Body param: `tree_filter` narrows results to traces containing at least one run
   * anywhere in the run tree (root or descendant) that matches this LangSmith filter
   * expression.
   */
  tree_filter?: string;

  /**
   * Header param: application/json, or text/event-stream (required when ai_search is
   * set)
   */
  Accept?: string;
}

export declare namespace Traces {
  export {
    type Trace as Trace,
    type TraceAggregates as TraceAggregates,
    type TraceListRunsResponse as TraceListRunsResponse,
    type TracesItemsCursorPostPagination as TracesItemsCursorPostPagination,
    type TraceListRunsParams as TraceListRunsParams,
    type TraceQueryParams as TraceQueryParams,
  };
}
