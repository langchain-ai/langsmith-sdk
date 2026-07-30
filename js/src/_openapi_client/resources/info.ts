// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { RequestOptions } from '../internal/request-options.js';

export class Info extends APIResource {
  /**
   * Returns information about the current LangSmith deployment: version, instance
   * feature flags, batch-ingest limits, and max SDK versions. Unauthenticated by
   * default; set FF_INFO_ENDPOINT_AUTH_REQUIRED=true to require auth.
   */
  list(options?: RequestOptions): APIPromise<InfoListResponse> {
    return this._client.get('/api/v1/info', options);
  }
}

export interface InfoListResponse {
  batch_ingest_config?: InfoListResponse.BatchIngestConfig;

  customer_info?: InfoListResponse.CustomerInfo;

  git_sha?: string;

  instance_flags?: { [key: string]: unknown };

  license_expiration_time?: string;

  sdk_versions?: InfoListResponse.SDKVersions;

  version?: string;
}

export namespace InfoListResponse {
  export interface BatchIngestConfig {
    scale_down_nempty_trigger?: number;

    scale_up_nthreads_limit?: number;

    scale_up_qsize_trigger?: number;

    size_limit?: number;

    size_limit_bytes?: number;

    use_multipart_endpoint?: boolean;
  }

  export interface CustomerInfo {
    customer_id?: string;

    customer_name?: string;
  }

  export interface SDKVersions {
    max_go_sdk_version?: string;

    max_java_sdk_version?: string;

    max_js_sdk_version?: string;

    max_python_sdk_version?: string;
  }
}

export declare namespace Info {
  export { type InfoListResponse as InfoListResponse };
}
