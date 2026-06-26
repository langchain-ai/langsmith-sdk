// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as BoxesAPI from './boxes.js';
import {
  BoxCreateParams,
  BoxCreateSnapshotParams,
  BoxGenerateServiceURLParams,
  BoxListParams,
  BoxUpdateParams,
  Boxes,
} from './boxes.js';
import * as RegistriesAPI from './registries.js';
import {
  Registries,
  RegistryCreateParams,
  RegistryListParams,
  RegistryListResponse,
  RegistryResponse,
  RegistryUpdateParams,
} from './registries.js';
import * as SnapshotsAPI from './snapshots.js';
import { SnapshotCreateParams, SnapshotListParams, Snapshots } from './snapshots.js';

export class Sandboxes extends APIResource {
  boxes: BoxesAPI.Boxes = new BoxesAPI.Boxes(this._client);
  registries: RegistriesAPI.Registries = new RegistriesAPI.Registries(this._client);
  snapshots: SnapshotsAPI.Snapshots = new SnapshotsAPI.Snapshots(this._client);
}

export interface SandboxListResponse {
  offset?: number;

  sandboxes?: Array<SandboxResponse>;
}

export interface SandboxResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  mem_bytes?: number;

  mount_config?: SandboxResponse.MountConfig;

  name?: string;

  proxy_config?: SandboxResponse.ProxyConfig;

  size_class?: string;

  snapshot_id?: string;

  status?: string;

  status_message?: string;

  stopped_at?: string;

  updated_at?: string;

  updated_by?: string;

  vcpus?: number;
}

export namespace SandboxResponse {
  export interface MountConfig {
    auth?: MountConfig.Auth;

    mounts?: Array<
      | MountConfig.SandboxapiS3BucketMountSpec
      | MountConfig.SandboxapiGcsBucketMountSpec
      | MountConfig.SandboxapiGitRepoMountSpec
    >;
  }

  export namespace MountConfig {
    export interface Auth {
      aws?: Auth.Aws;

      gcp?: Auth.Gcp;
    }

    export namespace Auth {
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
        service_account_json: Gcp.ServiceAccountJson;
      }

      export namespace Gcp {
        export interface ServiceAccountJson {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }
    }

    export interface SandboxapiS3BucketMountSpec {
      id: string;

      mount_path: string;

      s3: SandboxapiS3BucketMountSpec.S3;

      type: 's3' | 'gcs' | 'git';

      cache?: SandboxapiS3BucketMountSpec.Cache;

      gcs?: SandboxapiS3BucketMountSpec.Gcs;

      git?: SandboxapiS3BucketMountSpec.Git;

      read_only?: boolean;
    }

    export namespace SandboxapiS3BucketMountSpec {
      export interface S3 {
        bucket: string;

        region: string;

        endpoint_url?: string;

        path_style?: boolean;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Gcs {
        bucket: string;

        prefix?: string;
      }

      export interface Git {
        remote_url: string;

        ref?: Git.Ref;

        refresh_interval_seconds?: number;
      }

      export namespace Git {
        export interface Ref {
          name: string;

          type: 'branch' | 'tag';
        }
      }
    }

    export interface SandboxapiGcsBucketMountSpec {
      id: string;

      gcs: SandboxapiGcsBucketMountSpec.Gcs;

      mount_path: string;

      type: 's3' | 'gcs' | 'git';

      cache?: SandboxapiGcsBucketMountSpec.Cache;

      git?: SandboxapiGcsBucketMountSpec.Git;

      read_only?: boolean;

      s3?: SandboxapiGcsBucketMountSpec.S3;
    }

    export namespace SandboxapiGcsBucketMountSpec {
      export interface Gcs {
        bucket: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Git {
        remote_url: string;

        ref?: Git.Ref;

        refresh_interval_seconds?: number;
      }

      export namespace Git {
        export interface Ref {
          name: string;

          type: 'branch' | 'tag';
        }
      }

      export interface S3 {
        bucket: string;

        region: string;

        endpoint_url?: string;

        path_style?: boolean;

        prefix?: string;
      }
    }

    export interface SandboxapiGitRepoMountSpec {
      id: string;

      git: SandboxapiGitRepoMountSpec.Git;

      mount_path: string;

      type: 's3' | 'gcs' | 'git';

      cache?: SandboxapiGitRepoMountSpec.Cache;

      gcs?: SandboxapiGitRepoMountSpec.Gcs;

      read_only?: boolean;

      s3?: SandboxapiGitRepoMountSpec.S3;
    }

    export namespace SandboxapiGitRepoMountSpec {
      export interface Git {
        remote_url: string;

        ref?: Git.Ref;

        refresh_interval_seconds?: number;
      }

      export namespace Git {
        export interface Ref {
          name: string;

          type: 'branch' | 'tag';
        }
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Gcs {
        bucket: string;

        prefix?: string;
      }

      export interface S3 {
        bucket: string;

        region: string;

        endpoint_url?: string;

        path_style?: boolean;

        prefix?: string;
      }
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

      /**
       * MatchHosts is only accepted for header injection rules. Provider auth rules use
       * built-in host matching.
       */
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

export interface SandboxStatusResponse {
  status?: string;

  status_message?: string;
}

export interface ServiceURLResponse {
  token?: string;

  browser_url?: string;

  expires_at?: string;

  service_url?: string;
}

export interface SnapshotListResponse {
  offset?: number;

  snapshots?: Array<SnapshotResponse>;
}

export interface SnapshotResponse {
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

Sandboxes.Boxes = Boxes;
Sandboxes.Registries = Registries;
Sandboxes.Snapshots = Snapshots;

export declare namespace Sandboxes {
  export {
    type SandboxListResponse as SandboxListResponse,
    type SandboxResponse as SandboxResponse,
    type SandboxStatusResponse as SandboxStatusResponse,
    type ServiceURLResponse as ServiceURLResponse,
    type SnapshotListResponse as SnapshotListResponse,
    type SnapshotResponse as SnapshotResponse,
  };

  export {
    Boxes as Boxes,
    type BoxCreateParams as BoxCreateParams,
    type BoxUpdateParams as BoxUpdateParams,
    type BoxListParams as BoxListParams,
    type BoxCreateSnapshotParams as BoxCreateSnapshotParams,
    type BoxGenerateServiceURLParams as BoxGenerateServiceURLParams,
  };

  export {
    Registries as Registries,
    type RegistryListResponse as RegistryListResponse,
    type RegistryResponse as RegistryResponse,
    type RegistryCreateParams as RegistryCreateParams,
    type RegistryUpdateParams as RegistryUpdateParams,
    type RegistryListParams as RegistryListParams,
  };

  export {
    Snapshots as Snapshots,
    type SnapshotCreateParams as SnapshotCreateParams,
    type SnapshotListParams as SnapshotListParams,
  };
}
