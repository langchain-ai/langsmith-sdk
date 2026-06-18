// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RunsAPI from '../runs/runs.js';
import * as TracesRunsAPI from './runs.js';
import { RunListParams, Runs } from './runs.js';

export class Traces extends APIResource {
  runs: TracesRunsAPI.Runs = new TracesRunsAPI.Runs(this._client);
}

export interface QueryTraceResponseBody {
  /**
   * `items` lists runs in the trace for the requested time window, in `start_time`
   * order.
   */
  items?: Array<RunsAPI.QueryRunResponse>;
}

Traces.Runs = Runs;

export declare namespace Traces {
  export { type QueryTraceResponseBody as QueryTraceResponseBody };

  export { Runs as Runs, type RunListParams as RunListParams };
}
