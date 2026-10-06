// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { buildHeaders } from '../internal/headers.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class ProductFeedback extends APIResource {
  /**
   * **Alpha:** This endpoint is in active development and may change without notice.
   *
   * Submits concise product feedback with optional non-sensitive client details.
   */
  create(
    params: ProductFeedbackCreateParams,
    options?: RequestOptions,
  ): APIPromise<ProductFeedbackCreateResponse> {
    const { 'Idempotency-Key': idempotencyKey, ...body } = params;
    return this._client.post('/api/v1/platform/product-feedbacks', {
      body,
      ...options,
      headers: buildHeaders([
        { ...(idempotencyKey != null ? { 'Idempotency-Key': idempotencyKey } : undefined) },
        options?.headers,
      ]),
    });
  }

  /**
   * **Alpha:** This endpoint is in active development and may change without notice.
   */
  retrieve(id: string, options?: RequestOptions): APIPromise<ProductFeedbackRetrieveResponse> {
    return this._client.get(path`/api/v1/platform/product-feedbacks/${id}`, options);
  }
}

export interface ProductFeedbackCreateResponse {
  id: string;

  category: 'BUG' | 'FEATURE_REQUEST' | 'USABILITY' | 'DOCUMENTATION' | 'OTHER';

  created_at: string;

  message: string;

  source: 'LANGSMITH_CLI';

  client?: ProductFeedbackCreateResponse.Client;
}

export namespace ProductFeedbackCreateResponse {
  export interface Client {
    architecture?: string;

    os?: string;

    version?: string;
  }
}

export interface ProductFeedbackRetrieveResponse {
  id: string;

  category: 'BUG' | 'FEATURE_REQUEST' | 'USABILITY' | 'DOCUMENTATION' | 'OTHER';

  created_at: string;

  message: string;

  source: 'LANGSMITH_CLI';

  client?: ProductFeedbackRetrieveResponse.Client;
}

export namespace ProductFeedbackRetrieveResponse {
  export interface Client {
    architecture?: string;

    os?: string;

    version?: string;
  }
}

export interface ProductFeedbackCreateParams {
  /**
   * Body param
   */
  category: 'BUG' | 'FEATURE_REQUEST' | 'USABILITY' | 'DOCUMENTATION' | 'OTHER';

  /**
   * Body param
   */
  message: string;

  /**
   * Body param
   */
  source: 'LANGSMITH_CLI';

  /**
   * Body param
   */
  client?: ProductFeedbackCreateParams.Client;

  /**
   * Header param: Idempotency key
   */
  'Idempotency-Key'?: string;
}

export namespace ProductFeedbackCreateParams {
  export interface Client {
    architecture?: string;

    os?: string;

    version?: string;
  }
}

export declare namespace ProductFeedback {
  export {
    type ProductFeedbackCreateResponse as ProductFeedbackCreateResponse,
    type ProductFeedbackRetrieveResponse as ProductFeedbackRetrieveResponse,
    type ProductFeedbackCreateParams as ProductFeedbackCreateParams,
  };
}
