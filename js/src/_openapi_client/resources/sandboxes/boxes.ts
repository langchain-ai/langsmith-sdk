// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource';
import { APIPromise } from '../../core/api-promise';
import { buildHeaders } from '../../internal/headers';
import { RequestOptions } from '../../internal/request-options';
import { path } from '../../internal/utils/path';

export class Boxes extends APIResource {
  /**
   * Create a new sandbox from a snapshot. Provide at most one of `snapshot_id` or
   * `snapshot_name`; if neither is provided, the server uses the default static
   * blueprint.
   */
  create(body: BoxCreateParams, options?: RequestOptions): APIPromise<BoxCreateResponse> {
    return this._client.post('/v2/sandboxes/boxes', { body, ...options });
  }

  /**
   * Retrieve a sandbox by name. Stale provisioning sandboxes are auto-failed.
   */
  retrieve(name: string, options?: RequestOptions): APIPromise<BoxRetrieveResponse> {
    return this._client.get(path`/v2/sandboxes/boxes/${name}`, options);
  }

  /**
   * Update a sandbox's display name. The name must be unique within the tenant.
   */
  update(name: string, body: BoxUpdateParams, options?: RequestOptions): APIPromise<BoxUpdateResponse> {
    return this._client.patch(path`/v2/sandboxes/boxes/${name}`, { body, ...options });
  }

  /**
   * List sandboxes for the authenticated tenant, with optional filtering, sorting,
   * and pagination.
   */
  list(query: BoxListParams | null | undefined = {}, options?: RequestOptions): APIPromise<BoxListResponse> {
    return this._client.get('/v2/sandboxes/boxes', { query, ...options });
  }

  /**
   * Delete a sandbox by name or UUID. Tears down the sandbox runtime and removes the
   * DB record.
   */
  delete(name: string, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/v2/sandboxes/boxes/${name}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }

  /**
   * Create a snapshot by capturing the current state of a sandbox or promoting an
   * existing checkpoint.
   */
  createSnapshot(
    name: string,
    body: BoxCreateSnapshotParams,
    options?: RequestOptions,
  ): APIPromise<BoxCreateSnapshotResponse> {
    return this._client.post(path`/v2/sandboxes/boxes/${name}/snapshot`, { body, ...options });
  }

  /**
   * Create a short-lived JWT for accessing an HTTP service running on a specific
   * port inside a sandbox. Returns a browser_url (sets auth cookie via redirect), a
   * service_url (for use with the X-Langsmith-Sandbox-Service-Token header), the raw
   * token, and its expiry.
   */
  generateServiceURL(
    name: string,
    body: BoxGenerateServiceURLParams,
    options?: RequestOptions,
  ): APIPromise<BoxGenerateServiceURLResponse> {
    return this._client.post(path`/v2/sandboxes/boxes/${name}/service-url`, { body, ...options });
  }

  /**
   * Retrieve the lightweight status of a sandbox for polling.
   */
  getStatus(name: string, options?: RequestOptions): APIPromise<BoxGetStatusResponse> {
    return this._client.get(path`/v2/sandboxes/boxes/${name}/status`, options);
  }

  /**
   * Start a stopped or failed sandbox. This endpoint is not idempotent.
   */
  start(name: string, options?: RequestOptions): APIPromise<BoxStartResponse> {
    return this._client.post(path`/v2/sandboxes/boxes/${name}/start`, options);
  }

  /**
   * Stop a ready sandbox. This endpoint is not idempotent; the filesystem is
   * preserved for later restart.
   */
  stop(name: string, options?: RequestOptions): APIPromise<void> {
    return this._client.post(path`/v2/sandboxes/boxes/${name}/stop`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }
}

export interface BoxCreateResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mounts?: Array<BoxCreateResponse.Mount>;

  name?: string;

  proxy_config?: BoxCreateResponse.ProxyConfig;

  size_class?: string;

  snapshot_id?: string;

  status?: string;

  status_message?: string;

  stopped_at?: string;

  updated_at?: string;

  updated_by?: string;

  vcpus?: number;
}

export namespace BoxCreateResponse {
  export interface Mount {
    id: string;

    mount_path: string;

    s3: Mount.S3;

    type: 's3';

    cache?: Mount.Cache;

    read_only?: boolean;
  }

  export namespace Mount {
    export interface S3 {
      bucket: string;

      endpoint_url: string;

      region: string;

      path_style?: boolean;

      prefix?: string;
    }

    export interface Cache {
      max_size_bytes?: number;

      writeback_seconds?: number;
    }
  }

  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxRetrieveResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mounts?: Array<BoxRetrieveResponse.Mount>;

  name?: string;

  proxy_config?: BoxRetrieveResponse.ProxyConfig;

  size_class?: string;

  snapshot_id?: string;

  status?: string;

  status_message?: string;

  stopped_at?: string;

  updated_at?: string;

  updated_by?: string;

  vcpus?: number;
}

export namespace BoxRetrieveResponse {
  export interface Mount {
    id: string;

    mount_path: string;

    s3: Mount.S3;

    type: 's3';

    cache?: Mount.Cache;

    read_only?: boolean;
  }

  export namespace Mount {
    export interface S3 {
      bucket: string;

      endpoint_url: string;

      region: string;

      path_style?: boolean;

      prefix?: string;
    }

    export interface Cache {
      max_size_bytes?: number;

      writeback_seconds?: number;
    }
  }

  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxUpdateResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mounts?: Array<BoxUpdateResponse.Mount>;

  name?: string;

  proxy_config?: BoxUpdateResponse.ProxyConfig;

  size_class?: string;

  snapshot_id?: string;

  status?: string;

  status_message?: string;

  stopped_at?: string;

  updated_at?: string;

  updated_by?: string;

  vcpus?: number;
}

export namespace BoxUpdateResponse {
  export interface Mount {
    id: string;

    mount_path: string;

    s3: Mount.S3;

    type: 's3';

    cache?: Mount.Cache;

    read_only?: boolean;
  }

  export namespace Mount {
    export interface S3 {
      bucket: string;

      endpoint_url: string;

      region: string;

      path_style?: boolean;

      prefix?: string;
    }

    export interface Cache {
      max_size_bytes?: number;

      writeback_seconds?: number;
    }
  }

  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxListResponse {
  offset?: number;

  sandboxes?: Array<BoxListResponse.Sandbox>;
}

export namespace BoxListResponse {
  export interface Sandbox {
    id?: string;

    created_at?: string;

    created_by?: string;

    dataplane_url?: string;

    delete_after_stop_seconds?: number;

    fs_capacity_bytes?: number;

    idle_ttl_seconds?: number;

    mem_bytes?: number;

    mounts?: Array<Sandbox.Mount>;

    name?: string;

    proxy_config?: Sandbox.ProxyConfig;

    size_class?: string;

    snapshot_id?: string;

    status?: string;

    status_message?: string;

    stopped_at?: string;

    updated_at?: string;

    updated_by?: string;

    vcpus?: number;
  }

  export namespace Sandbox {
    export interface Mount {
      id: string;

      mount_path: string;

      s3: Mount.S3;

      type: 's3';

      cache?: Mount.Cache;

      read_only?: boolean;
    }

    export namespace Mount {
      export interface S3 {
        bucket: string;

        endpoint_url: string;

        region: string;

        path_style?: boolean;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }
    }

    export interface ProxyConfig {
      access_control?: ProxyConfig.AccessControl;

      callbacks?: Array<ProxyConfig.Callback>;

      no_proxy?: Array<string>;

      rules?: Array<ProxyConfig.Rule>;
    }

    export namespace ProxyConfig {
      export interface AccessControl {
        allow_list?: Array<string>;

        deny_list?: Array<string>;
      }

      export interface Callback {
        match_hosts: Array<string>;

        ttl_seconds: number;

        url: string;

        full_request?: boolean;

        request_headers?: Array<Callback.RequestHeader>;
      }

      export namespace Callback {
        export interface RequestHeader {
          name: string;

          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Rule {
        name: string;

        aws?: Rule.Aws;

        enabled?: boolean;

        gcp?: Rule.Gcp;

        headers?: Array<Rule.Header>;

        match_hosts?: Array<string>;

        match_paths?: Array<string>;

        type?: string;
      }

      export namespace Rule {
        export interface Aws {
          access_key_id: Aws.AccessKeyID;

          secret_access_key: Aws.SecretAccessKey;
        }

        export namespace Aws {
          export interface AccessKeyID {
            type: 'plaintext' | 'opaque' | 'workspace_secret';

            is_set?: boolean;

            value?: string;
          }

          export interface SecretAccessKey {
            type: 'plaintext' | 'opaque' | 'workspace_secret';

            is_set?: boolean;

            value?: string;
          }
        }

        export interface Gcp {
          scopes: Array<string>;

          service_account_json: Gcp.ServiceAccountJson;
        }

        export namespace Gcp {
          export interface ServiceAccountJson {
            type: 'plaintext' | 'opaque' | 'workspace_secret';

            is_set?: boolean;

            value?: string;
          }
        }

        export interface Header {
          name: string;

          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }
    }
  }
}

export interface BoxCreateSnapshotResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  docker_image?: string;

  fs_capacity_bytes?: number;

  fs_used_bytes?: number;

  image_digest?: string;

  /**
   * MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
   * state. A non-nil value is the canonical signal that this snapshot can
   * warm-restore from memory; nil means rootfs only.
   */
  memory_snapshot_size_bytes?: number;

  name?: string;

  registry_id?: string;

  source_sandbox_id?: string;

  status?: string;

  status_message?: string;

  updated_at?: string;
}

export interface BoxGenerateServiceURLResponse {
  token?: string;

  browser_url?: string;

  expires_at?: string;

  service_url?: string;
}

export interface BoxGetStatusResponse {
  status?: string;

  status_message?: string;
}

export interface BoxStartResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mounts?: Array<BoxStartResponse.Mount>;

  name?: string;

  proxy_config?: BoxStartResponse.ProxyConfig;

  size_class?: string;

  snapshot_id?: string;

  status?: string;

  status_message?: string;

  stopped_at?: string;

  updated_at?: string;

  updated_by?: string;

  vcpus?: number;
}

export namespace BoxStartResponse {
  export interface Mount {
    id: string;

    mount_path: string;

    s3: Mount.S3;

    type: 's3';

    cache?: Mount.Cache;

    read_only?: boolean;
  }

  export namespace Mount {
    export interface S3 {
      bucket: string;

      endpoint_url: string;

      region: string;

      path_style?: boolean;

      prefix?: string;
    }

    export interface Cache {
      max_size_bytes?: number;

      writeback_seconds?: number;
    }
  }

  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxCreateParams {
  delete_after_stop_seconds?: number;

  env_vars?: { [key: string]: string };

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mounts?: Array<BoxCreateParams.Mount>;

  name?: string;

  proxy_config?: BoxCreateParams.ProxyConfig;

  /**
   * RestoreMemory selects how the sandbox handles a snapshot's captured memory:
   *
   * nil → if-present: resume from memory when the snapshot has it, else cold-boot
   * (default). true → always: resume from memory; rejected if the snapshot has none.
   * false → never: always cold-boot.
   *
   * Applies to this request only.
   */
  restore_memory?: boolean;

  snapshot_id?: string;

  snapshot_name?: string;

  tag_value_ids?: Array<string>;

  vcpus?: number;
}

export namespace BoxCreateParams {
  export interface Mount {
    id: string;

    mount_path: string;

    s3: Mount.S3;

    type: 's3';

    cache?: Mount.Cache;

    read_only?: boolean;
  }

  export namespace Mount {
    export interface S3 {
      bucket: string;

      endpoint_url: string;

      region: string;

      path_style?: boolean;

      prefix?: string;
    }

    export interface Cache {
      max_size_bytes?: number;

      writeback_seconds?: number;
    }
  }

  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxUpdateParams {
  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  name?: string;

  proxy_config?: BoxUpdateParams.ProxyConfig;

  tag_value_ids?: Array<string>;

  vcpus?: number;
}

export namespace BoxUpdateParams {
  export interface ProxyConfig {
    access_control?: ProxyConfig.AccessControl;

    callbacks?: Array<ProxyConfig.Callback>;

    no_proxy?: Array<string>;

    rules?: Array<ProxyConfig.Rule>;
  }

  export namespace ProxyConfig {
    export interface AccessControl {
      allow_list?: Array<string>;

      deny_list?: Array<string>;
    }

    export interface Callback {
      match_hosts: Array<string>;

      ttl_seconds: number;

      url: string;

      full_request?: boolean;

      request_headers?: Array<Callback.RequestHeader>;
    }

    export namespace Callback {
      export interface RequestHeader {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }

    export interface Rule {
      name: string;

      aws?: Rule.Aws;

      enabled?: boolean;

      gcp?: Rule.Gcp;

      headers?: Array<Rule.Header>;

      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface Aws {
        access_key_id: Aws.AccessKeyID;

        secret_access_key: Aws.SecretAccessKey;
      }

      export namespace Aws {
        export interface AccessKeyID {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }

        export interface SecretAccessKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Gcp {
        scopes: Array<string>;

        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface Header {
        name: string;

        type: 'plaintext' | 'opaque' | 'workspace_secret';

        is_set?: boolean;

        value?: string;
      }
    }
  }
}

export interface BoxListParams {
  /**
   * Filter by creator identity. Only 'me' is supported.
   */
  created_by?: string;

  /**
   * Maximum number of results
   */
  limit?: number;

  /**
   * Filter by name substring
   */
  name_contains?: string;

  /**
   * Pagination offset
   */
  offset?: number;

  /**
   * Sort column (name, status, created_at)
   */
  sort_by?: string;

  /**
   * Sort direction (asc, desc)
   */
  sort_direction?: string;

  /**
   * Filter by status (provisioning, ready, failed, stopped, deleting)
   */
  status?: string;
}

export interface BoxCreateSnapshotParams {
  name: string;

  /**
   * if omitted, creates a fresh checkpoint from the running VM
   */
  checkpoint?: string;

  /**
   * sandbox-local Docker image to export
   */
  docker_image?: string;

  /**
   * required for Docker image export unless the sandbox has a capacity
   */
  fs_capacity_bytes?: number;

  /**
   * IncludeMemory, when true, captures a full VM memory snapshot alongside the
   * filesystem clone. Only honored when the sandbox is running AND Checkpoint is
   * omitted (i.e. a fresh in-VM checkpoint is requested). Defaults to false to keep
   * snapshots small unless memory restore is explicitly desired.
   */
  include_memory?: boolean;
}

export interface BoxGenerateServiceURLParams {
  expires_in_seconds?: number;

  port?: number;
}

export declare namespace Boxes {
  export {
    type BoxCreateResponse as BoxCreateResponse,
    type BoxRetrieveResponse as BoxRetrieveResponse,
    type BoxUpdateResponse as BoxUpdateResponse,
    type BoxListResponse as BoxListResponse,
    type BoxCreateSnapshotResponse as BoxCreateSnapshotResponse,
    type BoxGenerateServiceURLResponse as BoxGenerateServiceURLResponse,
    type BoxGetStatusResponse as BoxGetStatusResponse,
    type BoxStartResponse as BoxStartResponse,
    type BoxCreateParams as BoxCreateParams,
    type BoxUpdateParams as BoxUpdateParams,
    type BoxListParams as BoxListParams,
    type BoxCreateSnapshotParams as BoxCreateSnapshotParams,
    type BoxGenerateServiceURLParams as BoxGenerateServiceURLParams,
  };
}
