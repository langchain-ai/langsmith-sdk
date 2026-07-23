// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import { APIPromise } from '../../core/api-promise.js';
import { buildHeaders } from '../../internal/headers.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';
import * as RunsAPI_ from '../runs/runs.js';

export class Runs extends APIResource {
  /**
   * **Alpha:** The request and response contract may change; Returns one run within
   * the trace identified by the share token. The request supplies only the run ID
   * and that run's exact start_time coordinate.
   *
   * @example
   * ```ts
   * const run = await client.public.runs.retrieve(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   *   {
   *     share_token: '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   *     selects: ['string'],
   *     start_time: '2019-12-27T18:11:19.117Z',
   *   },
   * );
   * ```
   */
  retrieve(runID: string, params: RunRetrieveParams, options?: RequestOptions): APIPromise<RunsAPI_.Run> {
    const { share_token, Accept, ...query } = params;
    return this._client.get(path`/v2/public/${share_token}/run/${runID}`, {
      query,
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }

  /**
   * **Alpha:** The request and response contract may change; Returns all runs within
   * the trace identified by the share token. The share token supplies the tenant,
   * project, and trace scope.
   *
   * @example
   * ```ts
   * const response = await client.public.runs.query(
   *   '182bd5e5-6e1a-4fe4-a799-aa6d9a6ab26e',
   * );
   * ```
   */
  query(shareToken: string, params: RunQueryParams, options?: RequestOptions): APIPromise<RunQueryResponse> {
    const { Accept, ...body } = params;
    return this._client.post(path`/v2/public/${shareToken}/runs/v2/query`, {
      body,
      ...options,
      headers: buildHeaders([{ ...(Accept != null ? { Accept: Accept } : undefined) }, options?.headers]),
    });
  }
}

export interface RunQueryResponse {
  /**
   * `items` lists runs in the trace for the requested time window, in `start_time`
   * order.
   */
  items?: Array<RunsAPI_.Run>;
}

export interface RunRetrieveParams {
  /**
   * Path param: Share token UUID
   */
  share_token: string;

  /**
   * Query param: repeatable public run fields to include
   */
  selects: Array<string>;

  /**
   * Query param: Run start_time coordinate (RFC3339)
   */
  start_time: string;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export interface RunQueryParams {
  /**
   * Body param: `selects` lists which public run properties to include on each
   * returned run.
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
    | 'INPUTS_PREVIEW'
    | 'OUTPUTS_PREVIEW'
    | 'PARENT_RUN_ID'
    | 'PARENT_RUN_IDS'
    | 'PROJECT_ID'
    | 'TRACE_ID'
    | 'THREAD_ID'
    | 'DOTTED_ORDER'
    | 'IS_ROOT'
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
    | 'THREAD_EVALUATION_TIME'
    | 'FEEDBACK_STATS'
  >;

  /**
   * Header param: application/json
   */
  Accept?: string;
}

export declare namespace Runs {
  export {
    type RunQueryResponse as RunQueryResponse,
    type RunRetrieveParams as RunRetrieveParams,
    type RunQueryParams as RunQueryParams,
  };
}
