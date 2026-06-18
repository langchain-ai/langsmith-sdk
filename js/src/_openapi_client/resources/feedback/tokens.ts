// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as SessionsAPI from '../sessions/sessions.js';
import { APIPromise } from '../../core/api-promise.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Tokens extends APIResource {
  /**
   * Create a new feedback ingest token.
   */
  create(params: TokenCreateParams, options?: RequestOptions): APIPromise<TokenCreateResponse> {
    const body = 'body' in params ? params.body : params;
    return this._client.post('/api/v1/feedback/tokens', { body, ...options });
  }

  /**
   * Create a new feedback with a token.
   */
  retrieve(
    token: string,
    query: TokenRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<unknown> {
    return this._client.get(path`/api/v1/feedback/tokens/${token}`, { query, ...options });
  }

  /**
   * Create a new feedback with a token.
   */
  update(token: string, body: TokenUpdateParams, options?: RequestOptions): APIPromise<unknown> {
    return this._client.post(path`/api/v1/feedback/tokens/${token}`, { body, ...options });
  }

  /**
   * List all feedback ingest tokens for a run.
   */
  list(query: TokenListParams, options?: RequestOptions): APIPromise<TokenListResponse> {
    return this._client.get('/api/v1/feedback/tokens', { query, ...options });
  }
}

/**
 * Feedback ingest token create schema.
 */
export interface FeedbackIngestTokenCreateSchema {
  feedback_key: string;

  run_id: string;

  expires_at?: string | null;

  /**
   * Timedelta input.
   */
  expires_in?: SessionsAPI.TimedeltaInput | null;

  feedback_config?: FeedbackIngestTokenCreateSchema.FeedbackConfig | null;
}

export namespace FeedbackIngestTokenCreateSchema {
  export interface FeedbackConfig {
    /**
     * Enum for feedback types.
     */
    type: 'continuous' | 'categorical' | 'freeform';

    categories?: Array<FeedbackConfig.Category> | null;

    max?: number | null;

    min?: number | null;
  }

  export namespace FeedbackConfig {
    /**
     * Specific value and label pair for feedback
     */
    export interface Category {
      value: number;

      label?: string | null;
    }
  }
}

/**
 * Feedback ingest token schema.
 */
export interface FeedbackIngestTokenSchema {
  id: string;

  expires_at: string;

  feedback_key: string;

  url: string;
}

/**
 * Feedback ingest token schema.
 */
export type TokenCreateResponse = FeedbackIngestTokenSchema | Array<FeedbackIngestTokenSchema>;

export type TokenRetrieveResponse = unknown;

export type TokenUpdateResponse = unknown;

export type TokenListResponse = Array<FeedbackIngestTokenSchema>;

export type TokenCreateParams =
  | TokenCreateParams.FeedbackIngestTokenCreateSchema
  | TokenCreateParams.Variant1;

export declare namespace TokenCreateParams {
  export interface FeedbackIngestTokenCreateSchema {
    feedback_key: string;

    run_id: string;

    expires_at?: string | null;

    /**
     * Timedelta input.
     */
    expires_in?: SessionsAPI.TimedeltaInput | null;

    feedback_config?: FeedbackIngestTokenCreateSchema.FeedbackConfig | null;
  }

  export namespace FeedbackIngestTokenCreateSchema {
    export interface FeedbackConfig {
      /**
       * Enum for feedback types.
       */
      type: 'continuous' | 'categorical' | 'freeform';

      categories?: Array<FeedbackConfig.Category> | null;

      max?: number | null;

      min?: number | null;
    }

    export namespace FeedbackConfig {
      /**
       * Specific value and label pair for feedback
       */
      export interface Category {
        value: number;

        label?: string | null;
      }
    }
  }

  export interface Variant1 {
    body: Array<FeedbackIngestTokenCreateSchema>;
  }
}

export interface TokenRetrieveParams {
  comment?: string | null;

  correction?: string | null;

  score?: number | boolean | null;

  value?: number | boolean | string | null;
}

export interface TokenUpdateParams {
  comment?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  metadata?: { [key: string]: unknown } | null;

  score?: number | boolean | null;

  value?: number | boolean | string | null;
}

export interface TokenListParams {
  run_id: string;
}

export declare namespace Tokens {
  export {
    type FeedbackIngestTokenCreateSchema as FeedbackIngestTokenCreateSchema,
    type FeedbackIngestTokenSchema as FeedbackIngestTokenSchema,
    type TokenCreateResponse as TokenCreateResponse,
    type TokenRetrieveResponse as TokenRetrieveResponse,
    type TokenUpdateResponse as TokenUpdateResponse,
    type TokenListResponse as TokenListResponse,
    type TokenCreateParams as TokenCreateParams,
    type TokenRetrieveParams as TokenRetrieveParams,
    type TokenUpdateParams as TokenUpdateParams,
    type TokenListParams as TokenListParams,
  };
}
