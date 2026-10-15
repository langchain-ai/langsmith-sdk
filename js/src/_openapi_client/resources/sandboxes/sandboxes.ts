// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../core/resource.js';
import * as BoxesAPI from './boxes.js';
import {
  BoxCreateParams,
  BoxCreateSnapshotParams,
  BoxDeleteServiceURLParams,
  BoxGenerateDownloadURLParams,
  BoxGenerateServiceURLParams,
  BoxListParams,
  BoxListServiceURLsParams,
  BoxListServiceURLsResponse,
  BoxListServiceURLsResponsesItemsCursorGetPagination,
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
import {
  SnapshotCreateParams,
  SnapshotListParams,
  SnapshotRetrieveByNameResponse,
  Snapshots,
} from './snapshots.js';
import {
  ItemsCursorGetPagination,
  type ItemsCursorGetPaginationParams,
  PagePromise,
} from '../../core/pagination.js';
import { RequestOptions } from '../../internal/request-options.js';

export class Sandboxes extends APIResource {
  boxes: BoxesAPI.Boxes = new BoxesAPI.Boxes(this._client);
  registries: RegistriesAPI.Registries = new RegistriesAPI.Registries(this._client);
  snapshots: SnapshotsAPI.Snapshots = new SnapshotsAPI.Snapshots(this._client);

  /**
   * Returns priced usage per sandbox or snapshot and UTC hour in the half-open
   * requested interval. LCU uses the recorded compute amount for sandboxes;
   * snapshots have zero LCU. LSU allocates the recorded workspace storage amount
   * proportionally to attributed bytes, including checkpoints on their sandbox and
   * snapshots as separate resources. Resource filters preserve each resource's
   * share. Rate changes do not reprice recorded amounts. An access-filtered page can
   * have no items and a non-null next_cursor; continue until next_cursor is null.
   */
  listUsageCosts(
    query: SandboxListUsageCostsParams,
    options?: RequestOptions,
  ): PagePromise<SandboxListUsageCostsResponsesItemsCursorGetPagination, SandboxListUsageCostsResponse> {
    return this._client.getAPIList(
      '/api/v2/sandboxes/usage/costs',
      ItemsCursorGetPagination<SandboxListUsageCostsResponse>,
      { query, ...options },
    );
  }
}

export type SandboxListUsageCostsResponsesItemsCursorGetPagination =
  ItemsCursorGetPagination<SandboxListUsageCostsResponse>;

export type SandboxResponsesItemsCursorGetPagination = ItemsCursorGetPagination<SandboxResponse>;

export type SnapshotResponsesItemsCursorGetPagination = ItemsCursorGetPagination<SnapshotResponse>;

export interface DownloadURLResponse {
  token: string;

  download_url: string;

  /**
   * ExpiresAt is null for a link that never expires.
   */
  expires_at?: string | null;
}

export interface SandboxListResponse {
  /**
   * This page of sandboxes.
   */
  items?: Array<SandboxResponse>;

  /**
   * Cursor for the next page, or null on the last page. A non-null value is the only
   * signal that more pages exist. Treat it as opaque.
   */
  next_cursor?: string;

  /**
   * Deprecated: use next_cursor. Offset to request for the next page, or 0 when no
   * pages remain.
   */
  offset?: number;

  /**
   * Deprecated: use items. Duplicates items.
   */
  sandboxes?: Array<SandboxResponse>;
}

export interface SandboxResponse {
  id?: string;

  /**
   * AccessDelegation is the LangSmith access this sandbox was granted, absent when
   * it has none. It is reported exactly as it was requested at create.
   */
  access_delegation?: SandboxResponse.AccessDelegation;

  cpu_millicores?: number;

  created_at?: string;

  created_by?: string;

  dataplane_url?: string;

  delete_after_stop_seconds?: number;

  fs_capacity_bytes?: number;

  idle_ttl_seconds?: number;

  labels?: { [key: string]: string };

  mem_bytes?: number;

  mount_config?: SandboxResponse.MountConfig;

  name?: string;

  preserve_memory_on_stop?: boolean;

  proxy_config?: SandboxResponse.ProxyConfig;

  /**
   * RunConfig is what the sandbox's commands run with: the user, working directory
   * and base env beneath env_vars.
   */
  run_config?: SandboxResponse.RunConfig;

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
  /**
   * AccessDelegation is the LangSmith access this sandbox was granted, absent when
   * it has none. It is reported exactly as it was requested at create.
   */
  export interface AccessDelegation {
    mode: 'INHERIT' | 'EXPLICIT';

    permissions?: Array<string>;
  }

  export interface MountConfig {
    auth?: MountConfig.Auth;

    mounts?: Array<
      | MountConfig.SandboxapiS3BucketMountSpec
      | MountConfig.SandboxapiGcsBucketMountSpec
      | MountConfig.SandboxapiGitRepoMountSpec
      | MountConfig.SandboxapiContextHubRepoMountSpec
      | MountConfig.SandboxapiAzureBlobContainerMountSpec
    >;
  }

  export namespace MountConfig {
    export interface Auth {
      aws?: Auth.SandboxesSandboxAwsMountRoleAuthConfig | Auth.SandboxesSandboxAwsMountStaticAuthConfig;

      azure?:
        | Auth.SandboxesSandboxAzureMountWorkloadIdentityAuthConfig
        | Auth.SandboxesSandboxAzureMountAccountKeyAuthConfig
        | Auth.SandboxesSandboxAzureMountSasAuthConfig;

      gcp?:
        | Auth.SandboxesSandboxGcpMountWorkloadIdentityAuthConfig
        | Auth.SandboxesSandboxGcpMountServiceAccountAuthConfig;
    }

    export namespace Auth {
      export interface SandboxesSandboxAwsMountRoleAuthConfig {
        /**
         * IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
         * token LangSmith signs for this workspace; the role's trust policy must trust
         * LangSmith's issuer for the token subject. LangSmith scopes the credentials to
         * the configured S3 mounts. Mutually exclusive with static credentials, and cannot
         * be changed after creation.
         */
        role_arn: string;

        /**
         * SubjectScope picks the token subject the role trusts: "workspace" (the default)
         * or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
         * valid with role_arn.
         */
        subject_scope?: string;
      }

      export interface SandboxesSandboxAwsMountStaticAuthConfig {
        access_key_id: SandboxesSandboxAwsMountStaticAuthConfig.AccessKeyID;

        secret_access_key: SandboxesSandboxAwsMountStaticAuthConfig.SecretAccessKey;

        /**
         * IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
         * token LangSmith signs for this workspace; the role's trust policy must trust
         * LangSmith's issuer for the token subject. LangSmith scopes the credentials to
         * the configured S3 mounts. Mutually exclusive with static credentials, and cannot
         * be changed after creation.
         */
        role_arn?: '';
      }

      export namespace SandboxesSandboxAwsMountStaticAuthConfig {
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

      export interface SandboxesSandboxAzureMountWorkloadIdentityAuthConfig {
        /**
         * ClientID is the application (client) ID, a GUID, of the app registration or
         * user-assigned managed identity whose federated identity credential trusts
         * LangSmith's issuer. Required with tenant_id.
         */
        client_id: string;

        /**
         * TenantID is the Entra tenant (directory) ID, a GUID. Setting it selects workload
         * identity: LangSmith signs an OIDC token for this workspace and exchanges it at
         * Entra ID for storage access tokens of client_id. Cannot be changed after
         * creation.
         */
        tenant_id: string;

        /**
         * SubjectScope picks the token subject the federated credential trusts:
         * "workspace" (the default) or "tag:<tag value id>", which must be one of the
         * sandbox's tag_value_ids. Only valid with tenant_id.
         */
        subject_scope?: string;
      }

      export interface SandboxesSandboxAzureMountAccountKeyAuthConfig {
        account_key: SandboxesSandboxAzureMountAccountKeyAuthConfig.AccountKey;
      }

      export namespace SandboxesSandboxAzureMountAccountKeyAuthConfig {
        export interface AccountKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface SandboxesSandboxAzureMountSasAuthConfig {
        sas_token: SandboxesSandboxAzureMountSasAuthConfig.SasToken;
      }

      export namespace SandboxesSandboxAzureMountSasAuthConfig {
        export interface SasToken {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface SandboxesSandboxGcpMountWorkloadIdentityAuthConfig {
        /**
         * WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
         * workspace through Workload Identity Federation instead of a service account key:
         * //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
         * Mutually exclusive with service_account_json. Cannot be changed after creation.
         */
        workload_identity_provider: string;

        /**
         * ServiceAccountEmail is the service account to impersonate with the federated
         * token. Omit it to use the federated principal directly. Only valid with
         * workload_identity_provider.
         */
        service_account_email?: string;

        /**
         * SubjectScope picks the token subject the provider trusts: "workspace" (the
         * default) or "tag:<tag value id>", which must be one of the sandbox's
         * tag_value_ids. Only valid with workload_identity_provider.
         */
        subject_scope?: string;
      }

      export interface SandboxesSandboxGcpMountServiceAccountAuthConfig {
        service_account_json: SandboxesSandboxGcpMountServiceAccountAuthConfig.ServiceAccountJson;
      }

      export namespace SandboxesSandboxGcpMountServiceAccountAuthConfig {
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

      type: 's3' | 'gcs' | 'azure_blob' | 'git' | 'contexthub';

      azure_blob?: SandboxapiS3BucketMountSpec.AzureBlob;

      cache?: SandboxapiS3BucketMountSpec.Cache;

      contexthub?: SandboxapiS3BucketMountSpec.Contexthub;

      encryption?: SandboxapiS3BucketMountSpec.Encryption;

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

      export interface AzureBlob {
        container: string;

        /**
         * StorageAccount is the storage account name: 3 to 24 lowercase letters and
         * digits.
         */
        storage_account: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Contexthub {
        /**
         * Repo is the Context Hub repository to sync, as "owner/repo" (e.g. "-/my-agent",
         * where "-" is the current workspace). The repo's latest commit tree is mirrored
         * into the mount path.
         */
        repo: string;

        /**
         * InitialPullOnly syncs the repo once at startup instead of polling for updates
         * for the sandbox's lifetime.
         */
        initial_pull_only?: boolean;
      }

      export interface Encryption {
        /**
         * KMSKey is the key to encrypt uploads with. S3 mounts take a KMS key ARN in the
         * mount's region.
         */
        kms_key: string;
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

      type: 's3' | 'gcs' | 'azure_blob' | 'git' | 'contexthub';

      azure_blob?: SandboxapiGcsBucketMountSpec.AzureBlob;

      cache?: SandboxapiGcsBucketMountSpec.Cache;

      contexthub?: SandboxapiGcsBucketMountSpec.Contexthub;

      encryption?: SandboxapiGcsBucketMountSpec.Encryption;

      git?: SandboxapiGcsBucketMountSpec.Git;

      read_only?: boolean;

      s3?: SandboxapiGcsBucketMountSpec.S3;
    }

    export namespace SandboxapiGcsBucketMountSpec {
      export interface Gcs {
        bucket: string;

        prefix?: string;
      }

      export interface AzureBlob {
        container: string;

        /**
         * StorageAccount is the storage account name: 3 to 24 lowercase letters and
         * digits.
         */
        storage_account: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Contexthub {
        /**
         * Repo is the Context Hub repository to sync, as "owner/repo" (e.g. "-/my-agent",
         * where "-" is the current workspace). The repo's latest commit tree is mirrored
         * into the mount path.
         */
        repo: string;

        /**
         * InitialPullOnly syncs the repo once at startup instead of polling for updates
         * for the sandbox's lifetime.
         */
        initial_pull_only?: boolean;
      }

      export interface Encryption {
        /**
         * KMSKey is the key to encrypt uploads with. S3 mounts take a KMS key ARN in the
         * mount's region.
         */
        kms_key: string;
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

      type: 's3' | 'gcs' | 'azure_blob' | 'git' | 'contexthub';

      azure_blob?: SandboxapiGitRepoMountSpec.AzureBlob;

      cache?: SandboxapiGitRepoMountSpec.Cache;

      contexthub?: SandboxapiGitRepoMountSpec.Contexthub;

      encryption?: SandboxapiGitRepoMountSpec.Encryption;

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

      export interface AzureBlob {
        container: string;

        /**
         * StorageAccount is the storage account name: 3 to 24 lowercase letters and
         * digits.
         */
        storage_account: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Contexthub {
        /**
         * Repo is the Context Hub repository to sync, as "owner/repo" (e.g. "-/my-agent",
         * where "-" is the current workspace). The repo's latest commit tree is mirrored
         * into the mount path.
         */
        repo: string;

        /**
         * InitialPullOnly syncs the repo once at startup instead of polling for updates
         * for the sandbox's lifetime.
         */
        initial_pull_only?: boolean;
      }

      export interface Encryption {
        /**
         * KMSKey is the key to encrypt uploads with. S3 mounts take a KMS key ARN in the
         * mount's region.
         */
        kms_key: string;
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

    export interface SandboxapiContextHubRepoMountSpec {
      id: string;

      contexthub: SandboxapiContextHubRepoMountSpec.Contexthub;

      mount_path: string;

      type: 's3' | 'gcs' | 'azure_blob' | 'git' | 'contexthub';

      azure_blob?: SandboxapiContextHubRepoMountSpec.AzureBlob;

      cache?: SandboxapiContextHubRepoMountSpec.Cache;

      encryption?: SandboxapiContextHubRepoMountSpec.Encryption;

      gcs?: SandboxapiContextHubRepoMountSpec.Gcs;

      git?: SandboxapiContextHubRepoMountSpec.Git;

      read_only?: boolean;

      s3?: SandboxapiContextHubRepoMountSpec.S3;
    }

    export namespace SandboxapiContextHubRepoMountSpec {
      export interface Contexthub {
        /**
         * Repo is the Context Hub repository to sync, as "owner/repo" (e.g. "-/my-agent",
         * where "-" is the current workspace). The repo's latest commit tree is mirrored
         * into the mount path.
         */
        repo: string;

        /**
         * InitialPullOnly syncs the repo once at startup instead of polling for updates
         * for the sandbox's lifetime.
         */
        initial_pull_only?: boolean;
      }

      export interface AzureBlob {
        container: string;

        /**
         * StorageAccount is the storage account name: 3 to 24 lowercase letters and
         * digits.
         */
        storage_account: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Encryption {
        /**
         * KMSKey is the key to encrypt uploads with. S3 mounts take a KMS key ARN in the
         * mount's region.
         */
        kms_key: string;
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

      export interface S3 {
        bucket: string;

        region: string;

        endpoint_url?: string;

        path_style?: boolean;

        prefix?: string;
      }
    }

    export interface SandboxapiAzureBlobContainerMountSpec {
      id: string;

      azure_blob: SandboxapiAzureBlobContainerMountSpec.AzureBlob;

      mount_path: string;

      type: 's3' | 'gcs' | 'azure_blob' | 'git' | 'contexthub';

      cache?: SandboxapiAzureBlobContainerMountSpec.Cache;

      contexthub?: SandboxapiAzureBlobContainerMountSpec.Contexthub;

      encryption?: SandboxapiAzureBlobContainerMountSpec.Encryption;

      gcs?: SandboxapiAzureBlobContainerMountSpec.Gcs;

      git?: SandboxapiAzureBlobContainerMountSpec.Git;

      read_only?: boolean;

      s3?: SandboxapiAzureBlobContainerMountSpec.S3;
    }

    export namespace SandboxapiAzureBlobContainerMountSpec {
      export interface AzureBlob {
        container: string;

        /**
         * StorageAccount is the storage account name: 3 to 24 lowercase letters and
         * digits.
         */
        storage_account: string;

        prefix?: string;
      }

      export interface Cache {
        max_size_bytes?: number;

        writeback_seconds?: number;
      }

      export interface Contexthub {
        /**
         * Repo is the Context Hub repository to sync, as "owner/repo" (e.g. "-/my-agent",
         * where "-" is the current workspace). The repo's latest commit tree is mirrored
         * into the mount path.
         */
        repo: string;

        /**
         * InitialPullOnly syncs the repo once at startup instead of polling for updates
         * for the sandbox's lifetime.
         */
        initial_pull_only?: boolean;
      }

      export interface Encryption {
        /**
         * KMSKey is the key to encrypt uploads with. S3 mounts take a KMS key ARN in the
         * mount's region.
         */
        kms_key: string;
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

    /**
     * Description says what this configuration as a whole lets the sandbox reach,
     * complementing the per-rule descriptions. At most 1024 characters.
     */
    description?: string;

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

      aws?: Rule.SandboxesProxyAwsRoleConfig | Rule.SandboxesProxyAwsStaticConfig;

      azure?:
        | Rule.SandboxesProxyAzureWorkloadIdentityConfig
        | Rule.SandboxesProxyAzureAccountKeyConfig
        | Rule.SandboxesProxyAzureSasConfig;

      /**
       * Description says what this rule lets the sandbox reach, so an agent driving the
       * sandbox can be told its capabilities. At most 1024 characters.
       */
      description?: string;

      enabled?: boolean;

      /**
       * EnvVars are plaintext env vars set for every command in the sandbox while this
       * rule is enabled. Use them for tools that refuse to run unless a credential env
       * var is present (e.g. gh needs GH_TOKEN) even though this rule injects the real
       * credential on the wire — set a dummy value here so the command starts. Explicit
       * per-sandbox env_vars win over these, and provider-managed (AWS/GCP) vars win
       * over both.
       */
      env_vars?: { [key: string]: string };

      gcp?: Rule.SandboxesProxyGcpWorkloadIdentityConfig | Rule.SandboxesProxyGcpServiceAccountConfig;

      headers?: Array<Rule.Header>;

      /**
       * MatchHeaders restricts a header injection rule to requests carrying every listed
       * header, each written "name: value" with a lowercase name and an exact value.
       * Pair with headers of the same name to swap a placeholder the sandbox sends (e.g.
       * "authorization: Bearer account-b") for a real credential, so one host can serve
       * several accounts. Rules are evaluated in order and the first match wins.
       */
      match_headers?: Array<string>;

      /**
       * MatchHosts is only accepted for header injection rules. Provider auth rules use
       * built-in host matching.
       */
      match_hosts?: Array<string>;

      match_paths?: Array<string>;

      type?: string;
    }

    export namespace Rule {
      export interface SandboxesProxyAwsRoleConfig {
        /**
         * IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
         * token LangSmith signs for this workspace. The role's trust policy must trust
         * LangSmith's issuer for the token subject. Credentials renew automatically, and
         * access follows the role's effective AWS permissions. Mutually exclusive with
         * static keys, and cannot be changed after creation.
         */
        role_arn: string;

        /**
         * SubjectScope picks the token subject the role trusts: "workspace" (the default)
         * or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
         * valid with role_arn.
         */
        subject_scope?: string;
      }

      export interface SandboxesProxyAwsStaticConfig {
        access_key_id: SandboxesProxyAwsStaticConfig.AccessKeyID;

        secret_access_key: SandboxesProxyAwsStaticConfig.SecretAccessKey;

        /**
         * IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
         * token LangSmith signs for this workspace. The role's trust policy must trust
         * LangSmith's issuer for the token subject. Credentials renew automatically, and
         * access follows the role's effective AWS permissions. Mutually exclusive with
         * static keys, and cannot be changed after creation.
         */
        role_arn?: '';
      }

      export namespace SandboxesProxyAwsStaticConfig {
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

      export interface SandboxesProxyAzureWorkloadIdentityConfig {
        /**
         * ClientID is the application (client) ID, a GUID, of the app registration or
         * user-assigned managed identity whose federated identity credential trusts
         * LangSmith's issuer. Required with tenant_id.
         */
        client_id: string;

        /**
         * TenantID is the Entra tenant (directory) ID, a GUID. Setting it selects workload
         * identity: LangSmith signs an OIDC token for this workspace and exchanges it at
         * Entra ID for access tokens of client_id, so no secret is stored. Cannot be
         * changed after creation.
         */
        tenant_id: string;

        /**
         * Resources narrows the Entra resources access tokens are obtained for, from
         * https://storage.azure.com, https://vault.azure.net, https://management.azure.com
         * and https://cognitiveservices.azure.com. Defaults to all of them. Only valid
         * with tenant_id.
         */
        resources?: Array<
          | 'https://storage.azure.com'
          | 'https://vault.azure.net'
          | 'https://management.azure.com'
          | 'https://cognitiveservices.azure.com'
        >;

        /**
         * SubjectScope picks the token subject the federated credential trusts:
         * "workspace" (the default) or "tag:<tag value id>", which must be one of the
         * sandbox's tag_value_ids. Only valid with tenant_id.
         */
        subject_scope?: string;
      }

      export interface SandboxesProxyAzureAccountKeyConfig {
        account_key: SandboxesProxyAzureAccountKeyConfig.AccountKey;

        /**
         * StorageAccount is the storage account static credentials authenticate to:
         * requests to its blob, dfs, queue, table and file endpoints. Requires exactly one
         * of account_key (requests are signed with SharedKey) or sas_token (appended to
         * each request).
         */
        storage_account: string;
      }

      export namespace SandboxesProxyAzureAccountKeyConfig {
        export interface AccountKey {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface SandboxesProxyAzureSasConfig {
        sas_token: SandboxesProxyAzureSasConfig.SasToken;

        /**
         * StorageAccount is the storage account static credentials authenticate to:
         * requests to its blob, dfs, queue, table and file endpoints. Requires exactly one
         * of account_key (requests are signed with SharedKey) or sas_token (appended to
         * each request).
         */
        storage_account: string;
      }

      export namespace SandboxesProxyAzureSasConfig {
        export interface SasToken {
          type: 'plaintext' | 'opaque' | 'workspace_secret';

          is_set?: boolean;

          value?: string;
        }
      }

      export interface SandboxesProxyGcpWorkloadIdentityConfig {
        /**
         * WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
         * workspace through Workload Identity Federation instead of a service account key.
         * Use the full resource name:
         * //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
         * Cannot be changed after creation.
         */
        workload_identity_provider: string;

        /**
         * Scopes are the OAuth scopes requested for the access token. Omit them to use
         * https://www.googleapis.com/auth/cloud-platform.
         */
        scopes?: Array<string>;

        /**
         * ServiceAccountEmail is the service account to impersonate with the federated
         * token. Omit it to use the federated principal directly.
         */
        service_account_email?: string;

        /**
         * SubjectScope picks the token subject the provider trusts: "workspace" (the
         * default) or "tag:<tag value id>", which must be one of the sandbox's
         * tag_value_ids. Only valid with workload_identity_provider.
         */
        subject_scope?: string;
      }

      export interface SandboxesProxyGcpServiceAccountConfig {
        service_account_json: SandboxesProxyGcpServiceAccountConfig.ServiceAccountJson;

        /**
         * Scopes are the OAuth scopes requested for the access token. Omit them to use
         * https://www.googleapis.com/auth/cloud-platform.
         */
        scopes?: Array<string>;
      }

      export namespace SandboxesProxyGcpServiceAccountConfig {
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

  /**
   * RunConfig is what the sandbox's commands run with: the user, working directory
   * and base env beneath env_vars.
   */
  export interface RunConfig {
    env_vars?: { [key: string]: string };

    user?: string;

    work_dir?: string;
  }
}

export interface SandboxStatusResponse {
  status?: string;

  status_message?: string;
}

export interface ServiceURLResponse {
  /**
   * Token and ExpiresAt are empty in LangSmith login mode (no token is minted).
   */
  token?: string;

  /**
   * Access echoes the enabled LangSmith login level ("restricted"/"workspace");
   * omitted in token mode.
   */
  access?: 'restricted' | 'workspace';

  browser_url?: string;

  expires_at?: string;

  service_url?: string;
}

export interface SnapshotListResponse {
  /**
   * This page of snapshots.
   */
  items?: Array<SnapshotResponse>;

  /**
   * Cursor for the next page, or null on the last page. A non-null value is the only
   * signal that more pages exist. Treat it as opaque.
   */
  next_cursor?: string;

  /**
   * Deprecated: use next_cursor. Offset to request for the next page, or 0 when no
   * pages remain.
   */
  offset?: number;

  /**
   * Deprecated: use items. Duplicates items.
   */
  snapshots?: Array<SnapshotResponse>;
}

export interface SnapshotResponse {
  id?: string;

  created_at?: string;

  created_by?: string;

  /**
   * Description says what this snapshot's image can do, so a caller can hand it to
   * an agent as a capability summary.
   */
  description?: string;

  docker_image?: string;

  fs_capacity_bytes?: number;

  fs_used_bytes?: number;

  image_digest?: string;

  labels?: { [key: string]: string };

  /**
   * MemorySnapshotSizeBytes is non-nil iff the snapshot was captured with VM memory
   * state. A non-nil value is the canonical signal that this snapshot can
   * warm-restore from memory; nil means rootfs only.
   */
  memory_snapshot_size_bytes?: number;

  name?: string;

  registry_id?: string;

  /**
   * RunConfig is what sandboxes from this snapshot boot with. Absent on snapshots
   * built before it was recorded, which run as root with their own env.
   */
  run_config?: SnapshotResponse.RunConfig;

  source_sandbox_id?: string;

  status?: string;

  status_message?: string;

  /**
   * Tags currently resolving to this snapshot, under Name. A snapshot with no tags
   * is dangling — addressable only by id.
   */
  tags?: Array<string>;

  updated_at?: string;
}

export namespace SnapshotResponse {
  /**
   * RunConfig is what sandboxes from this snapshot boot with. Absent on snapshots
   * built before it was recorded, which run as root with their own env.
   */
  export interface RunConfig {
    env_vars?: { [key: string]: string };

    user?: string;

    work_dir?: string;
  }
}

export interface SandboxListUsageCostsResponse {
  /**
   * Recorded compute usage in LangSmith Compute Units (LCU), as a decimal string
   * with up to six fractional digits and trailing zeros omitted. Snapshots return
   * "0".
   */
  lcu: string;

  /**
   * Allocated storage usage in LangSmith Storage Units (LSU), as a decimal string
   * with up to six fractional digits and trailing zeros omitted.
   */
  lsu: string;

  period_start: string;

  resource_id: string;

  resource_type: 'SANDBOX' | 'SNAPSHOT';
}

export interface SandboxListUsageCostsParams extends ItemsCursorGetPaginationParams {
  /**
   * Exclusive RFC3339 end time; the range must not exceed 31 days
   */
  end_time: string;

  /**
   * Inclusive RFC3339 start time
   */
  start_time: string;

  /**
   * HOUR returns hourly buckets. RESOURCE sums each resource over the requested
   * interval and sets period_start to start_time.
   */
  granularity?: 'HOUR' | 'RESOURCE';

  /**
   * Include usage totals across the filtered interval (RESOURCE only). Omitted when
   * unrestricted resource access cannot be verified or the service does not support
   * totals.
   */
  include_totals?: boolean;

  /**
   * Resource UUID filter; repeat this parameter up to 100 times
   */
  resource_ids?: Array<string>;

  /**
   * Resource type filter
   */
  resource_type?: 'SANDBOX' | 'SNAPSHOT';
}

Sandboxes.Boxes = Boxes;
Sandboxes.Registries = Registries;
Sandboxes.Snapshots = Snapshots;

export declare namespace Sandboxes {
  export {
    type DownloadURLResponse as DownloadURLResponse,
    type SandboxListResponse as SandboxListResponse,
    type SandboxResponse as SandboxResponse,
    type SandboxStatusResponse as SandboxStatusResponse,
    type ServiceURLResponse as ServiceURLResponse,
    type SnapshotListResponse as SnapshotListResponse,
    type SnapshotResponse as SnapshotResponse,
    type SandboxListUsageCostsResponse as SandboxListUsageCostsResponse,
    type SandboxListUsageCostsResponsesItemsCursorGetPagination as SandboxListUsageCostsResponsesItemsCursorGetPagination,
    type SandboxListUsageCostsParams as SandboxListUsageCostsParams,
  };

  export {
    Boxes as Boxes,
    type BoxListServiceURLsResponse as BoxListServiceURLsResponse,
    type BoxListServiceURLsResponsesItemsCursorGetPagination as BoxListServiceURLsResponsesItemsCursorGetPagination,
    type BoxCreateParams as BoxCreateParams,
    type BoxUpdateParams as BoxUpdateParams,
    type BoxListParams as BoxListParams,
    type BoxCreateSnapshotParams as BoxCreateSnapshotParams,
    type BoxDeleteServiceURLParams as BoxDeleteServiceURLParams,
    type BoxGenerateDownloadURLParams as BoxGenerateDownloadURLParams,
    type BoxGenerateServiceURLParams as BoxGenerateServiceURLParams,
    type BoxListServiceURLsParams as BoxListServiceURLsParams,
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
    type SnapshotRetrieveByNameResponse as SnapshotRetrieveByNameResponse,
    type SnapshotCreateParams as SnapshotCreateParams,
    type SnapshotListParams as SnapshotListParams,
  };
}
