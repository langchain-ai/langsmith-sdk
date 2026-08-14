// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as RunsAPI from './runs.js';
import { RunQueryParams, RunQueryResponse, RunRetrieveParams, Runs } from './runs.js';

export class Public extends APIResource {
  runs: RunsAPI.Runs = new RunsAPI.Runs(this._client);
}

Public.Runs = Runs;

export declare namespace Public {
  export {
    Runs as Runs,
    type RunQueryResponse as RunQueryResponse,
    type RunRetrieveParams as RunRetrieveParams,
    type RunQueryParams as RunQueryParams,
  };
}
