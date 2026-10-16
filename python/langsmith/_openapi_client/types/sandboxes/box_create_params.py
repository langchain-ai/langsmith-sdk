# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Union, Iterable
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from ..._types import SequenceNotStr

__all__ = [
    "BoxCreateParams",
    "AccessDelegation",
    "MountConfig",
    "MountConfigAuth",
    "MountConfigAuthAws",
    "MountConfigAuthAwsSandboxesSandboxAwsMountRoleAuthConfig",
    "MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfig",
    "MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigAccessKeyID",
    "MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigSecretAccessKey",
    "MountConfigAuthAzure",
    "MountConfigAuthAzureSandboxesSandboxAzureMountWorkloadIdentityAuthConfig",
    "MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfig",
    "MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfigAccountKey",
    "MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfig",
    "MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfigSasToken",
    "MountConfigAuthGcp",
    "MountConfigAuthGcpSandboxesSandboxGcpMountWorkloadIdentityAuthConfig",
    "MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfig",
    "MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfigServiceAccountJson",
    "MountConfigMount",
    "MountConfigMountSandboxapiS3BucketMountSpec",
    "MountConfigMountSandboxapiS3BucketMountSpecS3",
    "MountConfigMountSandboxapiS3BucketMountSpecAzureBlob",
    "MountConfigMountSandboxapiS3BucketMountSpecCache",
    "MountConfigMountSandboxapiS3BucketMountSpecContexthub",
    "MountConfigMountSandboxapiS3BucketMountSpecEncryption",
    "MountConfigMountSandboxapiS3BucketMountSpecGcs",
    "MountConfigMountSandboxapiS3BucketMountSpecGit",
    "MountConfigMountSandboxapiS3BucketMountSpecGitRef",
    "MountConfigMountSandboxapiGcsBucketMountSpec",
    "MountConfigMountSandboxapiGcsBucketMountSpecGcs",
    "MountConfigMountSandboxapiGcsBucketMountSpecAzureBlob",
    "MountConfigMountSandboxapiGcsBucketMountSpecCache",
    "MountConfigMountSandboxapiGcsBucketMountSpecContexthub",
    "MountConfigMountSandboxapiGcsBucketMountSpecEncryption",
    "MountConfigMountSandboxapiGcsBucketMountSpecGit",
    "MountConfigMountSandboxapiGcsBucketMountSpecGitRef",
    "MountConfigMountSandboxapiGcsBucketMountSpecS3",
    "MountConfigMountSandboxapiGitRepoMountSpec",
    "MountConfigMountSandboxapiGitRepoMountSpecGit",
    "MountConfigMountSandboxapiGitRepoMountSpecGitRef",
    "MountConfigMountSandboxapiGitRepoMountSpecAzureBlob",
    "MountConfigMountSandboxapiGitRepoMountSpecCache",
    "MountConfigMountSandboxapiGitRepoMountSpecContexthub",
    "MountConfigMountSandboxapiGitRepoMountSpecEncryption",
    "MountConfigMountSandboxapiGitRepoMountSpecGcs",
    "MountConfigMountSandboxapiGitRepoMountSpecS3",
    "MountConfigMountSandboxapiContextHubRepoMountSpec",
    "MountConfigMountSandboxapiContextHubRepoMountSpecContexthub",
    "MountConfigMountSandboxapiContextHubRepoMountSpecAzureBlob",
    "MountConfigMountSandboxapiContextHubRepoMountSpecCache",
    "MountConfigMountSandboxapiContextHubRepoMountSpecEncryption",
    "MountConfigMountSandboxapiContextHubRepoMountSpecGcs",
    "MountConfigMountSandboxapiContextHubRepoMountSpecGit",
    "MountConfigMountSandboxapiContextHubRepoMountSpecGitRef",
    "MountConfigMountSandboxapiContextHubRepoMountSpecS3",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpec",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecAzureBlob",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecCache",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecContexthub",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecEncryption",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecGcs",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecGit",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecGitRef",
    "MountConfigMountSandboxapiAzureBlobContainerMountSpecS3",
    "ProxyConfig",
    "ProxyConfigAccessControl",
    "ProxyConfigCallback",
    "ProxyConfigCallbackRequestHeader",
    "ProxyConfigRule",
    "ProxyConfigRuleAws",
    "ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey",
    "ProxyConfigRuleAzure",
    "ProxyConfigRuleAzureSandboxesProxyAzureWorkloadIdentityConfig",
    "ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfig",
    "ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfigAccountKey",
    "ProxyConfigRuleAzureSandboxesProxyAzureSasConfig",
    "ProxyConfigRuleAzureSandboxesProxyAzureSasConfigSasToken",
    "ProxyConfigRuleGcp",
    "ProxyConfigRuleGcpSandboxesProxyGcpWorkloadIdentityConfig",
    "ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfig",
    "ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfigServiceAccountJson",
    "ProxyConfigRuleHeader",
    "RunConfig",
]


class BoxCreateParams(TypedDict, total=False):
    access_delegation: AccessDelegation
    """
    AccessDelegation lets code inside the sandbox call the LangSmith API as you,
    with at most the permissions granted here. Omit for no access.
    """

    cpu_millicores: int
    """CPUMillicores optionally requests CPU at millicore granularity (e.g.

    500 = 0.5 vCPU); takes precedence over VCPUs. Fractional (sub-vCPU) values are
    not available for every sandbox.
    """

    delete_after_stop_seconds: int

    env_vars: Dict[str, str]

    fs_capacity_bytes: int

    idle_ttl_seconds: int

    labels: Dict[str, str]
    """
    Labels are free-form key/value metadata persisted with the sandbox and returned
    on reads. Labels from the source snapshot are inherited unless overridden here.
    """

    mem_bytes: int
    """Memory for the sandbox, in bytes.

    Memory is tied to CPU at 4 GiB per vCPU: omit it and it follows that ratio; set
    it and it must stay within 50% of the ratio for the requested CPU, so a 1 vCPU
    sandbox accepts 2-6 GiB. Setting memory without CPU derives the CPU from the
    same ratio. Maximum 64 GiB.
    """

    mount_config: MountConfig

    name: str

    preserve_memory_on_stop: bool
    """
    PreserveMemoryOnStop, when true, suspends the sandbox's memory on a voluntary
    stop (idle timeout or explicit stop) so the next start resumes from where it
    left off. Default false discards memory and keeps only the filesystem, so the
    next start is a cold boot. Restarts triggered by infrastructure maintenance
    always preserve memory regardless of this setting.
    """

    proxy_config: ProxyConfig

    restore_memory: bool
    """RestoreMemory selects how the sandbox handles a snapshot's captured memory:

    nil → if-present: resume from memory when the snapshot has it, else cold-boot
    (default). true → always: resume from memory; rejected if the snapshot has none.
    false → never: always cold-boot.

    Applies to this request only.
    """

    run_config: RunConfig
    """
    RunConfig overrides the snapshot's run config for this sandbox: user and
    work_dir replace the snapshot's, env_vars merge over it. The result is what the
    sandbox boots with, and what a snapshot captured from it carries.
    """

    snapshot: str
    """Snapshot is a Docker-style name or name:tag reference to boot from.

    A bare name resolves to name:latest.
    """

    snapshot_id: str

    snapshot_name: str
    """
    SnapshotName is a synonym for Snapshot, accepted for compatibility with clients
    that predate it. Set one or the other.
    """

    tag_value_ids: SequenceNotStr[str]

    vcpus: int


class AccessDelegation(TypedDict, total=False):
    """
    AccessDelegation lets code inside the sandbox call the LangSmith API as you, with at most the permissions granted here. Omit for no access.
    """

    mode: Required[Literal["INHERIT", "EXPLICIT"]]

    permissions: SequenceNotStr[str]


class MountConfigAuthAwsSandboxesSandboxAwsMountRoleAuthConfig(TypedDict, total=False):
    role_arn: Required[str]
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace; the role's trust policy must trust
    LangSmith's issuer for the token subject. LangSmith scopes the credentials to
    the configured S3 mounts. Mutually exclusive with static credentials, and cannot
    be changed after creation.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the role trusts: "workspace" (the default)
    or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
    valid with role_arn.
    """


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfig(TypedDict, total=False):
    access_key_id: Required[MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigAccessKeyID]

    secret_access_key: Required[MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigSecretAccessKey]

    role_arn: Literal[""]
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace; the role's trust policy must trust
    LangSmith's issuer for the token subject. LangSmith scopes the credentials to
    the configured S3 mounts. Mutually exclusive with static credentials, and cannot
    be changed after creation.
    """


MountConfigAuthAws: TypeAlias = Union[
    MountConfigAuthAwsSandboxesSandboxAwsMountRoleAuthConfig, MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfig
]


class MountConfigAuthAzureSandboxesSandboxAzureMountWorkloadIdentityAuthConfig(TypedDict, total=False):
    client_id: Required[str]
    """
    ClientID is the application (client) ID, a GUID, of the app registration or
    user-assigned managed identity whose federated identity credential trusts
    LangSmith's issuer. Required with tenant_id.
    """

    tenant_id: Required[str]
    """TenantID is the Entra tenant (directory) ID, a GUID.

    Setting it selects workload identity: LangSmith signs an OIDC token for this
    workspace and exchanges it at Entra ID for storage access tokens of client_id.
    Cannot be changed after creation.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the federated credential trusts:
    "workspace" (the default) or "tag:<tag value id>", which must be one of the
    sandbox's tag_value_ids. Only valid with tenant_id.
    """


class MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfigAccountKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfig(TypedDict, total=False):
    account_key: Required[MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfigAccountKey]


class MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfigSasToken(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfig(TypedDict, total=False):
    sas_token: Required[MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfigSasToken]


MountConfigAuthAzure: TypeAlias = Union[
    MountConfigAuthAzureSandboxesSandboxAzureMountWorkloadIdentityAuthConfig,
    MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfig,
    MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfig,
]


class MountConfigAuthGcpSandboxesSandboxGcpMountWorkloadIdentityAuthConfig(TypedDict, total=False):
    workload_identity_provider: Required[str]
    """
    WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
    workspace through Workload Identity Federation instead of a service account key:
    //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
    Mutually exclusive with service_account_json. Cannot be changed after creation.
    """

    service_account_email: str
    """
    ServiceAccountEmail is the service account to impersonate with the federated
    token. Omit it to use the federated principal directly. Only valid with
    workload_identity_provider.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the provider trusts: "workspace" (the
    default) or "tag:<tag value id>", which must be one of the sandbox's
    tag_value_ids. Only valid with workload_identity_provider.
    """


class MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfigServiceAccountJson(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfig(TypedDict, total=False):
    service_account_json: Required[MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfigServiceAccountJson]


MountConfigAuthGcp: TypeAlias = Union[
    MountConfigAuthGcpSandboxesSandboxGcpMountWorkloadIdentityAuthConfig,
    MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfig,
]


class MountConfigAuth(TypedDict, total=False):
    aws: MountConfigAuthAws

    azure: MountConfigAuthAzure

    gcp: MountConfigAuthGcp


class MountConfigMountSandboxapiS3BucketMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiS3BucketMountSpecAzureBlob(TypedDict, total=False):
    container: Required[str]

    storage_account: Required[str]
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: str


class MountConfigMountSandboxapiS3BucketMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


class MountConfigMountSandboxapiS3BucketMountSpecContexthub(TypedDict, total=False):
    repo: Required[str]
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: bool
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiS3BucketMountSpecEncryption(TypedDict, total=False):
    kms_key: Required[str]
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiS3BucketMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiS3BucketMountSpecGitRef(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["branch", "tag"]]


class MountConfigMountSandboxapiS3BucketMountSpecGit(TypedDict, total=False):
    remote_url: Required[str]

    ref: MountConfigMountSandboxapiS3BucketMountSpecGitRef

    refresh_interval_seconds: int


class MountConfigMountSandboxapiS3BucketMountSpec(TypedDict, total=False):
    id: Required[str]

    mount_path: Required[str]

    s3: Required[MountConfigMountSandboxapiS3BucketMountSpecS3]

    type: Required[Literal["s3", "gcs", "azure_blob", "git", "contexthub"]]

    azure_blob: MountConfigMountSandboxapiS3BucketMountSpecAzureBlob

    cache: MountConfigMountSandboxapiS3BucketMountSpecCache

    contexthub: MountConfigMountSandboxapiS3BucketMountSpecContexthub

    encryption: MountConfigMountSandboxapiS3BucketMountSpecEncryption

    gcs: MountConfigMountSandboxapiS3BucketMountSpecGcs

    git: MountConfigMountSandboxapiS3BucketMountSpecGit

    read_only: bool


class MountConfigMountSandboxapiGcsBucketMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiGcsBucketMountSpecAzureBlob(TypedDict, total=False):
    container: Required[str]

    storage_account: Required[str]
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: str


class MountConfigMountSandboxapiGcsBucketMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


class MountConfigMountSandboxapiGcsBucketMountSpecContexthub(TypedDict, total=False):
    repo: Required[str]
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: bool
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiGcsBucketMountSpecEncryption(TypedDict, total=False):
    kms_key: Required[str]
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiGcsBucketMountSpecGitRef(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["branch", "tag"]]


class MountConfigMountSandboxapiGcsBucketMountSpecGit(TypedDict, total=False):
    remote_url: Required[str]

    ref: MountConfigMountSandboxapiGcsBucketMountSpecGitRef

    refresh_interval_seconds: int


class MountConfigMountSandboxapiGcsBucketMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiGcsBucketMountSpec(TypedDict, total=False):
    id: Required[str]

    gcs: Required[MountConfigMountSandboxapiGcsBucketMountSpecGcs]

    mount_path: Required[str]

    type: Required[Literal["s3", "gcs", "azure_blob", "git", "contexthub"]]

    azure_blob: MountConfigMountSandboxapiGcsBucketMountSpecAzureBlob

    cache: MountConfigMountSandboxapiGcsBucketMountSpecCache

    contexthub: MountConfigMountSandboxapiGcsBucketMountSpecContexthub

    encryption: MountConfigMountSandboxapiGcsBucketMountSpecEncryption

    git: MountConfigMountSandboxapiGcsBucketMountSpecGit

    read_only: bool

    s3: MountConfigMountSandboxapiGcsBucketMountSpecS3


class MountConfigMountSandboxapiGitRepoMountSpecGitRef(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["branch", "tag"]]


class MountConfigMountSandboxapiGitRepoMountSpecGit(TypedDict, total=False):
    remote_url: Required[str]

    ref: MountConfigMountSandboxapiGitRepoMountSpecGitRef

    refresh_interval_seconds: int


class MountConfigMountSandboxapiGitRepoMountSpecAzureBlob(TypedDict, total=False):
    container: Required[str]

    storage_account: Required[str]
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: str


class MountConfigMountSandboxapiGitRepoMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


class MountConfigMountSandboxapiGitRepoMountSpecContexthub(TypedDict, total=False):
    repo: Required[str]
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: bool
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiGitRepoMountSpecEncryption(TypedDict, total=False):
    kms_key: Required[str]
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiGitRepoMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiGitRepoMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiGitRepoMountSpec(TypedDict, total=False):
    id: Required[str]

    git: Required[MountConfigMountSandboxapiGitRepoMountSpecGit]

    mount_path: Required[str]

    type: Required[Literal["s3", "gcs", "azure_blob", "git", "contexthub"]]

    azure_blob: MountConfigMountSandboxapiGitRepoMountSpecAzureBlob

    cache: MountConfigMountSandboxapiGitRepoMountSpecCache

    contexthub: MountConfigMountSandboxapiGitRepoMountSpecContexthub

    encryption: MountConfigMountSandboxapiGitRepoMountSpecEncryption

    gcs: MountConfigMountSandboxapiGitRepoMountSpecGcs

    read_only: bool

    s3: MountConfigMountSandboxapiGitRepoMountSpecS3


class MountConfigMountSandboxapiContextHubRepoMountSpecContexthub(TypedDict, total=False):
    repo: Required[str]
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: bool
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiContextHubRepoMountSpecAzureBlob(TypedDict, total=False):
    container: Required[str]

    storage_account: Required[str]
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: str


class MountConfigMountSandboxapiContextHubRepoMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


class MountConfigMountSandboxapiContextHubRepoMountSpecEncryption(TypedDict, total=False):
    kms_key: Required[str]
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiContextHubRepoMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiContextHubRepoMountSpecGitRef(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["branch", "tag"]]


class MountConfigMountSandboxapiContextHubRepoMountSpecGit(TypedDict, total=False):
    remote_url: Required[str]

    ref: MountConfigMountSandboxapiContextHubRepoMountSpecGitRef

    refresh_interval_seconds: int


class MountConfigMountSandboxapiContextHubRepoMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiContextHubRepoMountSpec(TypedDict, total=False):
    id: Required[str]

    contexthub: Required[MountConfigMountSandboxapiContextHubRepoMountSpecContexthub]

    mount_path: Required[str]

    type: Required[Literal["s3", "gcs", "azure_blob", "git", "contexthub"]]

    azure_blob: MountConfigMountSandboxapiContextHubRepoMountSpecAzureBlob

    cache: MountConfigMountSandboxapiContextHubRepoMountSpecCache

    encryption: MountConfigMountSandboxapiContextHubRepoMountSpecEncryption

    gcs: MountConfigMountSandboxapiContextHubRepoMountSpecGcs

    git: MountConfigMountSandboxapiContextHubRepoMountSpecGit

    read_only: bool

    s3: MountConfigMountSandboxapiContextHubRepoMountSpecS3


class MountConfigMountSandboxapiAzureBlobContainerMountSpecAzureBlob(TypedDict, total=False):
    container: Required[str]

    storage_account: Required[str]
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: str


class MountConfigMountSandboxapiAzureBlobContainerMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


class MountConfigMountSandboxapiAzureBlobContainerMountSpecContexthub(TypedDict, total=False):
    repo: Required[str]
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: bool
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiAzureBlobContainerMountSpecEncryption(TypedDict, total=False):
    kms_key: Required[str]
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGitRef(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["branch", "tag"]]


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGit(TypedDict, total=False):
    remote_url: Required[str]

    ref: MountConfigMountSandboxapiAzureBlobContainerMountSpecGitRef

    refresh_interval_seconds: int


class MountConfigMountSandboxapiAzureBlobContainerMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiAzureBlobContainerMountSpec(TypedDict, total=False):
    id: Required[str]

    azure_blob: Required[MountConfigMountSandboxapiAzureBlobContainerMountSpecAzureBlob]

    mount_path: Required[str]

    type: Required[Literal["s3", "gcs", "azure_blob", "git", "contexthub"]]

    cache: MountConfigMountSandboxapiAzureBlobContainerMountSpecCache

    contexthub: MountConfigMountSandboxapiAzureBlobContainerMountSpecContexthub

    encryption: MountConfigMountSandboxapiAzureBlobContainerMountSpecEncryption

    gcs: MountConfigMountSandboxapiAzureBlobContainerMountSpecGcs

    git: MountConfigMountSandboxapiAzureBlobContainerMountSpecGit

    read_only: bool

    s3: MountConfigMountSandboxapiAzureBlobContainerMountSpecS3


MountConfigMount: TypeAlias = Union[
    MountConfigMountSandboxapiS3BucketMountSpec,
    MountConfigMountSandboxapiGcsBucketMountSpec,
    MountConfigMountSandboxapiGitRepoMountSpec,
    MountConfigMountSandboxapiContextHubRepoMountSpec,
    MountConfigMountSandboxapiAzureBlobContainerMountSpec,
]


class MountConfig(TypedDict, total=False):
    auth: MountConfigAuth

    mounts: Iterable[MountConfigMount]


class ProxyConfigAccessControl(TypedDict, total=False):
    allow_list: SequenceNotStr[str]

    deny_list: SequenceNotStr[str]


class ProxyConfigCallbackRequestHeader(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigCallback(TypedDict, total=False):
    match_hosts: Required[SequenceNotStr[str]]

    ttl_seconds: Required[int]

    url: Required[str]

    full_request: bool

    request_headers: Iterable[ProxyConfigCallbackRequestHeader]


class ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig(TypedDict, total=False):
    role_arn: Required[str]
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace. The role's trust policy must trust
    LangSmith's issuer for the token subject. Credentials renew automatically, and
    access follows the role's effective AWS permissions. Mutually exclusive with
    static keys, and cannot be changed after creation.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the role trusts: "workspace" (the default)
    or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
    valid with role_arn.
    """


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig(TypedDict, total=False):
    access_key_id: Required[ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID]

    secret_access_key: Required[ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey]

    role_arn: Literal[""]
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace. The role's trust policy must trust
    LangSmith's issuer for the token subject. Credentials renew automatically, and
    access follows the role's effective AWS permissions. Mutually exclusive with
    static keys, and cannot be changed after creation.
    """


ProxyConfigRuleAws: TypeAlias = Union[
    ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig, ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig
]


class ProxyConfigRuleAzureSandboxesProxyAzureWorkloadIdentityConfig(TypedDict, total=False):
    client_id: Required[str]
    """
    ClientID is the application (client) ID, a GUID, of the app registration or
    user-assigned managed identity whose federated identity credential trusts
    LangSmith's issuer. Required with tenant_id.
    """

    tenant_id: Required[str]
    """TenantID is the Entra tenant (directory) ID, a GUID.

    Setting it selects workload identity: LangSmith signs an OIDC token for this
    workspace and exchanges it at Entra ID for access tokens of client_id, so no
    secret is stored. Cannot be changed after creation.
    """

    resources: List[
        Literal[
            "https://storage.azure.com",
            "https://vault.azure.net",
            "https://management.azure.com",
            "https://cognitiveservices.azure.com",
        ]
    ]
    """
    Resources narrows the Entra resources access tokens are obtained for, from
    https://storage.azure.com, https://vault.azure.net, https://management.azure.com
    and https://cognitiveservices.azure.com. Defaults to all of them. Only valid
    with tenant_id.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the federated credential trusts:
    "workspace" (the default) or "tag:<tag value id>", which must be one of the
    sandbox's tag_value_ids. Only valid with tenant_id.
    """


class ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfigAccountKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfig(TypedDict, total=False):
    account_key: Required[ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfigAccountKey]

    storage_account: Required[str]
    """
    StorageAccount is the storage account static credentials authenticate to:
    requests to its blob, dfs, queue, table and file endpoints. Requires exactly one
    of account_key (requests are signed with SharedKey) or sas_token (appended to
    each request).
    """


class ProxyConfigRuleAzureSandboxesProxyAzureSasConfigSasToken(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAzureSandboxesProxyAzureSasConfig(TypedDict, total=False):
    sas_token: Required[ProxyConfigRuleAzureSandboxesProxyAzureSasConfigSasToken]

    storage_account: Required[str]
    """
    StorageAccount is the storage account static credentials authenticate to:
    requests to its blob, dfs, queue, table and file endpoints. Requires exactly one
    of account_key (requests are signed with SharedKey) or sas_token (appended to
    each request).
    """


ProxyConfigRuleAzure: TypeAlias = Union[
    ProxyConfigRuleAzureSandboxesProxyAzureWorkloadIdentityConfig,
    ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfig,
    ProxyConfigRuleAzureSandboxesProxyAzureSasConfig,
]


class ProxyConfigRuleGcpSandboxesProxyGcpWorkloadIdentityConfig(TypedDict, total=False):
    workload_identity_provider: Required[str]
    """
    WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
    workspace through Workload Identity Federation instead of a service account key.
    Use the full resource name:
    //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
    Cannot be changed after creation.
    """

    scopes: SequenceNotStr[str]
    """Scopes are the OAuth scopes requested for the access token.

    Omit them to use https://www.googleapis.com/auth/cloud-platform.
    """

    service_account_email: str
    """
    ServiceAccountEmail is the service account to impersonate with the federated
    token. Omit it to use the federated principal directly.
    """

    subject_scope: str
    """
    SubjectScope picks the token subject the provider trusts: "workspace" (the
    default) or "tag:<tag value id>", which must be one of the sandbox's
    tag_value_ids. Only valid with workload_identity_provider.
    """


class ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfigServiceAccountJson(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfig(TypedDict, total=False):
    service_account_json: Required[ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfigServiceAccountJson]

    scopes: SequenceNotStr[str]
    """Scopes are the OAuth scopes requested for the access token.

    Omit them to use https://www.googleapis.com/auth/cloud-platform.
    """


ProxyConfigRuleGcp: TypeAlias = Union[
    ProxyConfigRuleGcpSandboxesProxyGcpWorkloadIdentityConfig, ProxyConfigRuleGcpSandboxesProxyGcpServiceAccountConfig
]


class ProxyConfigRuleHeader(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRule(TypedDict, total=False):
    name: Required[str]

    aws: ProxyConfigRuleAws

    azure: ProxyConfigRuleAzure

    description: str
    """
    Description says what this rule lets the sandbox reach, so an agent driving the
    sandbox can be told its capabilities. At most 1024 characters.
    """

    enabled: bool

    env_vars: Dict[str, str]
    """
    EnvVars are plaintext env vars set for every command in the sandbox while this
    rule is enabled. Use them for tools that refuse to run unless a credential env
    var is present (e.g. gh needs GH_TOKEN) even though this rule injects the real
    credential on the wire — set a dummy value here so the command starts. Explicit
    per-sandbox env_vars win over these, and provider-managed (AWS/GCP) vars win
    over both.
    """

    gcp: ProxyConfigRuleGcp

    headers: Iterable[ProxyConfigRuleHeader]

    match_headers: SequenceNotStr[str]
    """
    MatchHeaders restricts a header injection rule to requests carrying every listed
    header, each written "name: value" with a lowercase name and an exact value.
    Pair with headers of the same name to swap a placeholder the sandbox sends (e.g.
    "authorization: Bearer account-b") for a real credential, so one host can serve
    several accounts. Rules are evaluated in order and the first match wins.
    """

    match_hosts: SequenceNotStr[str]
    """MatchHosts is only accepted for header injection rules.

    Provider auth rules use built-in host matching.
    """

    match_paths: SequenceNotStr[str]

    type: str


class ProxyConfig(TypedDict, total=False):
    access_control: ProxyConfigAccessControl

    callbacks: Iterable[ProxyConfigCallback]

    description: str
    """
    Description says what this configuration as a whole lets the sandbox reach,
    complementing the per-rule descriptions. At most 1024 characters.
    """

    no_proxy: SequenceNotStr[str]

    rules: Iterable[ProxyConfigRule]


class RunConfig(TypedDict, total=False):
    """
    RunConfig overrides the snapshot's run config for this sandbox: user and
    work_dir replace the snapshot's, env_vars merge over it. The result is
    what the sandbox boots with, and what a snapshot captured from it carries.
    """

    env_vars: Dict[str, str]

    user: str

    work_dir: str
