// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as TracesAPI from './traces.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Runs extends APIResource {
  /**
   * **Alpha:** The request and response contract may change; Returns runs for a
   * trace ID within min/max start time. Optional `filter`; repeatable `selects` to
   * select fields to return.
   */
  list(
    traceID: string,
    params: RunListParams,
    options?: RequestOptions,
  ): APIPromise<TracesAPI.QueryTraceResponseBody> {
    const { Accept, ...query } = params;
    return this._client.get(path`/v2/traces/${traceID}/runs`, {
      query,
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }
}

export interface RunListParams {
  /**
   * Query param: `max_start_time` is the inclusive upper bound for run `start_time`
   * (RFC3339 date-time).
   */
  max_start_time: string;

  /**
   * Query param: `min_start_time` is the inclusive lower bound for run `start_time`
   * (RFC3339 date-time).
   */
  min_start_time: string;

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
    | 'SHARE_URL'
    | 'FEEDBACK_STATS'
  >;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export declare namespace Runs {
  export { type RunListParams as RunListParams };
}
