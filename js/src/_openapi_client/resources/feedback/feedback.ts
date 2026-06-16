// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as ConfigsAPI from './configs.js';
import { ConfigDeleteParams, Configs } from './configs.js';
import * as TokensAPI from './tokens.js';
import {
  FeedbackIngestTokenCreateSchema,
  FeedbackIngestTokenSchema,
  TokenCreateParams,
  TokenCreateResponse,
  TokenListParams,
  TokenListResponse,
  TokenRetrieveParams,
  TokenRetrieveResponse,
  TokenUpdateParams,
  TokenUpdateResponse,
  Tokens,
} from './tokens.js';
import { APIPromise } from '../../core/api-promise.js';
import {
  OffsetPaginationTopLevelArray,
  type OffsetPaginationTopLevelArrayParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';
import { path } from '../../internal/utils/path.js';

export class Feedback extends APIResource {
  tokens: TokensAPI.Tokens = new TokensAPI.Tokens(this._client);
  configs: ConfigsAPI.Configs = new ConfigsAPI.Configs(this._client);

  /**
   * Create a new feedback.
   */
  create(body: FeedbackCreateParams, options?: RequestOptions): APIPromise<FeedbackSchema> {
    return this._client.post('/api/v1/feedback', { body, ...options });
  }

  /**
   * Get a specific feedback.
   */
  retrieve(
    feedbackID: string,
    query: FeedbackRetrieveParams | null | undefined = {},
    options?: RequestOptions,
  ): APIPromise<FeedbackSchema> {
    return this._client.get(path`/api/v1/feedback/${feedbackID}`, { query, ...options });
  }

  /**
   * Replace an existing feedback entry with a new, modified entry.
   */
  update(
    feedbackID: string,
    body: FeedbackUpdateParams,
    options?: RequestOptions,
  ): APIPromise<FeedbackSchema> {
    return this._client.patch(path`/api/v1/feedback/${feedbackID}`, { body, ...options });
  }

  /**
   * List all Feedback by query params.
   */
  list(
    query: FeedbackListParams | null | undefined = {},
    options?: RequestOptions,
  ): PagePromise<FeedbackSchemasOffsetPaginationTopLevelArray, FeedbackSchema> {
    return this._client.getAPIList('/api/v1/feedback', OffsetPaginationTopLevelArray<FeedbackSchema>, {
      query,
      ...options,
    });
  }

  /**
   * Delete a feedback.
   */
  delete(feedbackID: string, options?: RequestOptions): APIPromise<unknown> {
    return this._client.delete(path`/api/v1/feedback/${feedbackID}`, options);
  }
}

export type FeedbackSchemasOffsetPaginationTopLevelArray = OffsetPaginationTopLevelArray<FeedbackSchema>;

/**
 * API feedback source.
 */
export interface APIFeedbackSource {
  metadata?: { [key: string]: unknown } | null;

  type?: 'api';
}

/**
 * Feedback from the LangChainPlus App.
 */
export interface AppFeedbackSource {
  metadata?: { [key: string]: unknown } | null;

  type?: 'app';
}

/**
 * Auto eval feedback source.
 */
export interface AutoEvalFeedbackSource {
  metadata?: { [key: string]: unknown } | null;

  type?: 'auto_eval';
}

/**
 * Schema used for creating feedback.
 */
export interface FeedbackCreateSchema {
  key: string;

  id?: string;

  comment?: string | null;

  comparative_experiment_id?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  created_at?: string;

  do_not_extend_trace_retention?: boolean;

  error?: boolean | null;

  feedback_config?: FeedbackCreateSchema.FeedbackConfig | null;

  feedback_group_id?: string | null;

  /**
   * Feedback from the LangChainPlus App.
   */
  feedback_source?:
    | AppFeedbackSource
    | APIFeedbackSource
    | ModelFeedbackSource
    | AutoEvalFeedbackSource
    | null;

  modified_at?: string;

  run_id?: string | null;

  score?: number | boolean | null;

  session_id?: string | null;

  start_time?: string | null;

  trace_id?: string | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackCreateSchema {
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
 * Enum for feedback levels.
 */
export type FeedbackLevel = 'run' | 'session';

/**
 * Schema for getting feedback.
 */
export interface FeedbackSchema {
  id: string;

  key: string;

  comment?: string | null;

  comparative_experiment_id?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  created_at?: string;

  extra?: { [key: string]: unknown } | null;

  feedback_group_id?: string | null;

  /**
   * The feedback source loaded from the database.
   */
  feedback_source?: FeedbackSchema.FeedbackSource | null;

  feedback_thread_id?: string | null;

  is_root?: boolean;

  modified_at?: string;

  run_id?: string | null;

  score?: number | boolean | null;

  session_id?: string | null;

  start_time?: string | null;

  trace_id?: string | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackSchema {
  /**
   * The feedback source loaded from the database.
   */
  export interface FeedbackSource {
    ls_user_id?: string | null;

    metadata?: { [key: string]: unknown } | null;

    type?: string | null;

    user_id?: string | null;

    user_name?: string | null;
  }
}

/**
 * Model feedback source.
 */
export interface ModelFeedbackSource {
  metadata?: { [key: string]: unknown } | null;

  type?: 'model';
}

/**
 * Enum for feedback source types.
 */
export type SourceType = 'api' | 'model' | 'app' | 'auto_eval';

export type FeedbackDeleteResponse = unknown;

export interface FeedbackCreateParams {
  key: string;

  id?: string;

  comment?: string | null;

  comparative_experiment_id?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  created_at?: string;

  do_not_extend_trace_retention?: boolean;

  error?: boolean | null;

  feedback_config?: FeedbackCreateParams.FeedbackConfig | null;

  feedback_group_id?: string | null;

  /**
   * Feedback from the LangChainPlus App.
   */
  feedback_source?:
    | AppFeedbackSource
    | APIFeedbackSource
    | ModelFeedbackSource
    | AutoEvalFeedbackSource
    | null;

  modified_at?: string;

  run_id?: string | null;

  score?: number | boolean | null;

  session_id?: string | null;

  start_time?: string | null;

  trace_id?: string | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackCreateParams {
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

export interface FeedbackRetrieveParams {
  include_user_names?: boolean | null;
}

export interface FeedbackUpdateParams {
  comment?: string | null;

  correction?: { [key: string]: unknown } | string | null;

  feedback_config?: FeedbackUpdateParams.FeedbackConfig | null;

  score?: number | boolean | null;

  value?: number | boolean | string | { [key: string]: unknown } | null;
}

export namespace FeedbackUpdateParams {
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

export interface FeedbackListParams extends OffsetPaginationTopLevelArrayParams {
  comparative_experiment_id?: string | null;

  has_comment?: boolean | null;

  has_score?: boolean | null;

  include_user_names?: boolean | null;

  key?: Array<string> | null;

  /**
   * Enum for feedback levels.
   */
  level?: FeedbackLevel | null;

  max_created_at?: string | null;

  min_created_at?: string | null;

  run?: Array<string> | string | null;

  session?: Array<string> | string | null;

  source?: Array<SourceType> | null;

  user?: Array<string> | null;
}

Feedback.Tokens = Tokens;
Feedback.Configs = Configs;

export declare namespace Feedback {
  export {
    type APIFeedbackSource as APIFeedbackSource,
    type AppFeedbackSource as AppFeedbackSource,
    type AutoEvalFeedbackSource as AutoEvalFeedbackSource,
    type FeedbackCreateSchema as FeedbackCreateSchema,
    type FeedbackLevel as FeedbackLevel,
    type FeedbackSchema as FeedbackSchema,
    type ModelFeedbackSource as ModelFeedbackSource,
    type SourceType as SourceType,
    type FeedbackDeleteResponse as FeedbackDeleteResponse,
    type FeedbackSchemasOffsetPaginationTopLevelArray as FeedbackSchemasOffsetPaginationTopLevelArray,
    type FeedbackCreateParams as FeedbackCreateParams,
    type FeedbackRetrieveParams as FeedbackRetrieveParams,
    type FeedbackUpdateParams as FeedbackUpdateParams,
    type FeedbackListParams as FeedbackListParams,
  };

  export {
    Tokens as Tokens,
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

  export { Configs as Configs, type ConfigDeleteParams as ConfigDeleteParams };
}
