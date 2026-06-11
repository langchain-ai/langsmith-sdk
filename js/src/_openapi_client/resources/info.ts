// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource';
import { APIPromise } from '../core/api-promise';
import { RequestOptions } from '../internal/request-options';

export class Info extends APIResource {
  /**
   * Get information about the current deployment of LangSmith.
   */
  list(options?: RequestOptions): APIPromise<InfoListResponse> {
    return this._client.get('/api/v1/info', options);
  }
}

/**
 * The LangSmith server info.
 */
export interface InfoListResponse {
  version: string;

  /**
   * Batch ingest config.
   */
  batch_ingest_config?: InfoListResponse.BatchIngestConfig;

  /**
   * Customer info.
   */
  customer_info?: InfoListResponse.CustomerInfo | null;

  git_sha?: string | null;

  instance_flags?: { [key: string]: unknown };

  license_expiration_time?: string | null;
}

export namespace InfoListResponse {
  /**
   * Batch ingest config.
   */
  export interface BatchIngestConfig {
    scale_down_nempty_trigger?: number;

    scale_up_nthreads_limit?: number;

    scale_up_qsize_trigger?: number;

    size_limit?: number;

    size_limit_bytes?: number;

    use_multipart_endpoint?: boolean;
  }

  /**
   * Customer info.
   */
  export interface CustomerInfo {
    customer_id: string;

    customer_name: string;
  }
}

export declare namespace Info {
  export { type InfoListResponse as InfoListResponse };
}
