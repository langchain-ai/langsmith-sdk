// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import type { Langsmith } from '../client.js';

export abstract class APIResource {
  protected _client: Langsmith;

  constructor(client: Langsmith) {
    this._client = client;
  }
}
