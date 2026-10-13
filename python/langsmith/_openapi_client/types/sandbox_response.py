# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from typing_extensions import Literal, TypeAlias

from .._models import BaseModel

__all__ = [
    "SandboxResponse",
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
    "ProxyConfigRuleGcpServiceAccountJson",
    "ProxyConfigRuleHeader",
    "RunConfig",
]


class AccessDelegation(BaseModel):
    """
    AccessDelegation is the LangSmith access this sandbox was granted, absent when it has none. It is reported exactly as it was requested at create.
    """

    mode: Literal["INHERIT", "EXPLICIT"]

    permissions: Optional[List[str]] = None


class MountConfigAuthAwsSandboxesSandboxAwsMountRoleAuthConfig(BaseModel):
    role_arn: str
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace; the role's trust policy must trust
    LangSmith's issuer for the token subject. LangSmith scopes the credentials to
    the configured S3 mounts. Mutually exclusive with static credentials, and cannot
    be changed after creation.
    """

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the role trusts: "workspace" (the default)
    or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
    valid with role_arn.
    """


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigAccessKeyID(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigSecretAccessKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfig(BaseModel):
    access_key_id: MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigAccessKeyID

    secret_access_key: MountConfigAuthAwsSandboxesSandboxAwsMountStaticAuthConfigSecretAccessKey

    role_arn: Optional[Literal[""]] = None
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


class MountConfigAuthAzureSandboxesSandboxAzureMountWorkloadIdentityAuthConfig(BaseModel):
    client_id: str
    """
    ClientID is the application (client) ID, a GUID, of the app registration or
    user-assigned managed identity whose federated identity credential trusts
    LangSmith's issuer. Required with tenant_id.
    """

    tenant_id: str
    """TenantID is the Entra tenant (directory) ID, a GUID.

    Setting it selects workload identity: LangSmith signs an OIDC token for this
    workspace and exchanges it at Entra ID for storage access tokens of client_id.
    Cannot be changed after creation.
    """

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the federated credential trusts:
    "workspace" (the default) or "tag:<tag value id>", which must be one of the
    sandbox's tag_value_ids. Only valid with tenant_id.
    """


class MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfigAccountKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfig(BaseModel):
    account_key: MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfigAccountKey


class MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfigSasToken(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfig(BaseModel):
    sas_token: MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfigSasToken


MountConfigAuthAzure: TypeAlias = Union[
    MountConfigAuthAzureSandboxesSandboxAzureMountWorkloadIdentityAuthConfig,
    MountConfigAuthAzureSandboxesSandboxAzureMountAccountKeyAuthConfig,
    MountConfigAuthAzureSandboxesSandboxAzureMountSasAuthConfig,
]


class MountConfigAuthGcpSandboxesSandboxGcpMountWorkloadIdentityAuthConfig(BaseModel):
    workload_identity_provider: str
    """
    WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
    workspace through Workload Identity Federation instead of a service account key:
    //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
    Mutually exclusive with service_account_json. Cannot be changed after creation.
    """

    service_account_email: Optional[str] = None
    """
    ServiceAccountEmail is the service account to impersonate with the federated
    token. Omit it to use the federated principal directly. Only valid with
    workload_identity_provider.
    """

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the provider trusts: "workspace" (the
    default) or "tag:<tag value id>", which must be one of the sandbox's
    tag_value_ids. Only valid with workload_identity_provider.
    """


class MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfigServiceAccountJson(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfig(BaseModel):
    service_account_json: MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfigServiceAccountJson


MountConfigAuthGcp: TypeAlias = Union[
    MountConfigAuthGcpSandboxesSandboxGcpMountWorkloadIdentityAuthConfig,
    MountConfigAuthGcpSandboxesSandboxGcpMountServiceAccountAuthConfig,
]


class MountConfigAuth(BaseModel):
    aws: Optional[MountConfigAuthAws] = None

    azure: Optional[MountConfigAuthAzure] = None

    gcp: Optional[MountConfigAuthGcp] = None


class MountConfigMountSandboxapiS3BucketMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiS3BucketMountSpecAzureBlob(BaseModel):
    container: str

    storage_account: str
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: Optional[str] = None


class MountConfigMountSandboxapiS3BucketMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


class MountConfigMountSandboxapiS3BucketMountSpecContexthub(BaseModel):
    repo: str
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: Optional[bool] = None
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiS3BucketMountSpecEncryption(BaseModel):
    kms_key: str
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiS3BucketMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiS3BucketMountSpecGitRef(BaseModel):
    name: str

    type: Literal["branch", "tag"]


class MountConfigMountSandboxapiS3BucketMountSpecGit(BaseModel):
    remote_url: str

    ref: Optional[MountConfigMountSandboxapiS3BucketMountSpecGitRef] = None

    refresh_interval_seconds: Optional[int] = None


class MountConfigMountSandboxapiS3BucketMountSpec(BaseModel):
    id: str

    mount_path: str

    s3: MountConfigMountSandboxapiS3BucketMountSpecS3

    type: Literal["s3", "gcs", "azure_blob", "git", "contexthub"]

    azure_blob: Optional[MountConfigMountSandboxapiS3BucketMountSpecAzureBlob] = None

    cache: Optional[MountConfigMountSandboxapiS3BucketMountSpecCache] = None

    contexthub: Optional[MountConfigMountSandboxapiS3BucketMountSpecContexthub] = None

    encryption: Optional[MountConfigMountSandboxapiS3BucketMountSpecEncryption] = None

    gcs: Optional[MountConfigMountSandboxapiS3BucketMountSpecGcs] = None

    git: Optional[MountConfigMountSandboxapiS3BucketMountSpecGit] = None

    read_only: Optional[bool] = None


class MountConfigMountSandboxapiGcsBucketMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGcsBucketMountSpecAzureBlob(BaseModel):
    container: str

    storage_account: str
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGcsBucketMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


class MountConfigMountSandboxapiGcsBucketMountSpecContexthub(BaseModel):
    repo: str
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: Optional[bool] = None
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiGcsBucketMountSpecEncryption(BaseModel):
    kms_key: str
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiGcsBucketMountSpecGitRef(BaseModel):
    name: str

    type: Literal["branch", "tag"]


class MountConfigMountSandboxapiGcsBucketMountSpecGit(BaseModel):
    remote_url: str

    ref: Optional[MountConfigMountSandboxapiGcsBucketMountSpecGitRef] = None

    refresh_interval_seconds: Optional[int] = None


class MountConfigMountSandboxapiGcsBucketMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGcsBucketMountSpec(BaseModel):
    id: str

    gcs: MountConfigMountSandboxapiGcsBucketMountSpecGcs

    mount_path: str

    type: Literal["s3", "gcs", "azure_blob", "git", "contexthub"]

    azure_blob: Optional[MountConfigMountSandboxapiGcsBucketMountSpecAzureBlob] = None

    cache: Optional[MountConfigMountSandboxapiGcsBucketMountSpecCache] = None

    contexthub: Optional[MountConfigMountSandboxapiGcsBucketMountSpecContexthub] = None

    encryption: Optional[MountConfigMountSandboxapiGcsBucketMountSpecEncryption] = None

    git: Optional[MountConfigMountSandboxapiGcsBucketMountSpecGit] = None

    read_only: Optional[bool] = None

    s3: Optional[MountConfigMountSandboxapiGcsBucketMountSpecS3] = None


class MountConfigMountSandboxapiGitRepoMountSpecGitRef(BaseModel):
    name: str

    type: Literal["branch", "tag"]


class MountConfigMountSandboxapiGitRepoMountSpecGit(BaseModel):
    remote_url: str

    ref: Optional[MountConfigMountSandboxapiGitRepoMountSpecGitRef] = None

    refresh_interval_seconds: Optional[int] = None


class MountConfigMountSandboxapiGitRepoMountSpecAzureBlob(BaseModel):
    container: str

    storage_account: str
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGitRepoMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


class MountConfigMountSandboxapiGitRepoMountSpecContexthub(BaseModel):
    repo: str
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: Optional[bool] = None
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiGitRepoMountSpecEncryption(BaseModel):
    kms_key: str
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiGitRepoMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGitRepoMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGitRepoMountSpec(BaseModel):
    id: str

    git: MountConfigMountSandboxapiGitRepoMountSpecGit

    mount_path: str

    type: Literal["s3", "gcs", "azure_blob", "git", "contexthub"]

    azure_blob: Optional[MountConfigMountSandboxapiGitRepoMountSpecAzureBlob] = None

    cache: Optional[MountConfigMountSandboxapiGitRepoMountSpecCache] = None

    contexthub: Optional[MountConfigMountSandboxapiGitRepoMountSpecContexthub] = None

    encryption: Optional[MountConfigMountSandboxapiGitRepoMountSpecEncryption] = None

    gcs: Optional[MountConfigMountSandboxapiGitRepoMountSpecGcs] = None

    read_only: Optional[bool] = None

    s3: Optional[MountConfigMountSandboxapiGitRepoMountSpecS3] = None


class MountConfigMountSandboxapiContextHubRepoMountSpecContexthub(BaseModel):
    repo: str
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: Optional[bool] = None
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiContextHubRepoMountSpecAzureBlob(BaseModel):
    container: str

    storage_account: str
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: Optional[str] = None


class MountConfigMountSandboxapiContextHubRepoMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


class MountConfigMountSandboxapiContextHubRepoMountSpecEncryption(BaseModel):
    kms_key: str
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiContextHubRepoMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiContextHubRepoMountSpecGitRef(BaseModel):
    name: str

    type: Literal["branch", "tag"]


class MountConfigMountSandboxapiContextHubRepoMountSpecGit(BaseModel):
    remote_url: str

    ref: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecGitRef] = None

    refresh_interval_seconds: Optional[int] = None


class MountConfigMountSandboxapiContextHubRepoMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiContextHubRepoMountSpec(BaseModel):
    id: str

    contexthub: MountConfigMountSandboxapiContextHubRepoMountSpecContexthub

    mount_path: str

    type: Literal["s3", "gcs", "azure_blob", "git", "contexthub"]

    azure_blob: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecAzureBlob] = None

    cache: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecCache] = None

    encryption: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecEncryption] = None

    gcs: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecGcs] = None

    git: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecGit] = None

    read_only: Optional[bool] = None

    s3: Optional[MountConfigMountSandboxapiContextHubRepoMountSpecS3] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpecAzureBlob(BaseModel):
    container: str

    storage_account: str
    """
    StorageAccount is the storage account name: 3 to 24 lowercase letters and
    digits.
    """

    prefix: Optional[str] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpecContexthub(BaseModel):
    repo: str
    """Repo is the Context Hub repository to sync, as "owner/repo" (e.g.

    "-/my-agent", where "-" is the current workspace). The repo's latest commit tree
    is mirrored into the mount path.
    """

    initial_pull_only: Optional[bool] = None
    """
    InitialPullOnly syncs the repo once at startup instead of polling for updates
    for the sandbox's lifetime.
    """


class MountConfigMountSandboxapiAzureBlobContainerMountSpecEncryption(BaseModel):
    kms_key: str
    """KMSKey is the key to encrypt uploads with.

    S3 mounts take a KMS key ARN in the mount's region.
    """


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGitRef(BaseModel):
    name: str

    type: Literal["branch", "tag"]


class MountConfigMountSandboxapiAzureBlobContainerMountSpecGit(BaseModel):
    remote_url: str

    ref: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecGitRef] = None

    refresh_interval_seconds: Optional[int] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiAzureBlobContainerMountSpec(BaseModel):
    id: str

    azure_blob: MountConfigMountSandboxapiAzureBlobContainerMountSpecAzureBlob

    mount_path: str

    type: Literal["s3", "gcs", "azure_blob", "git", "contexthub"]

    cache: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecCache] = None

    contexthub: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecContexthub] = None

    encryption: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecEncryption] = None

    gcs: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecGcs] = None

    git: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecGit] = None

    read_only: Optional[bool] = None

    s3: Optional[MountConfigMountSandboxapiAzureBlobContainerMountSpecS3] = None


MountConfigMount: TypeAlias = Union[
    MountConfigMountSandboxapiS3BucketMountSpec,
    MountConfigMountSandboxapiGcsBucketMountSpec,
    MountConfigMountSandboxapiGitRepoMountSpec,
    MountConfigMountSandboxapiContextHubRepoMountSpec,
    MountConfigMountSandboxapiAzureBlobContainerMountSpec,
]


class MountConfig(BaseModel):
    auth: Optional[MountConfigAuth] = None

    mounts: Optional[List[MountConfigMount]] = None


class ProxyConfigAccessControl(BaseModel):
    allow_list: Optional[List[str]] = None

    deny_list: Optional[List[str]] = None


class ProxyConfigCallbackRequestHeader(BaseModel):
    name: str

    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigCallback(BaseModel):
    match_hosts: List[str]

    ttl_seconds: int

    url: str

    full_request: Optional[bool] = None

    request_headers: Optional[List[ProxyConfigCallbackRequestHeader]] = None


class ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig(BaseModel):
    role_arn: str
    """
    IAM role to assume with AssumeRoleWithWebIdentity, using a short-lived OIDC
    token LangSmith signs for this workspace. The role's trust policy must trust
    LangSmith's issuer for the token subject. Credentials renew automatically, and
    access follows the role's effective AWS permissions. Mutually exclusive with
    static keys, and cannot be changed after creation.
    """

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the role trusts: "workspace" (the default)
    or "tag:<tag value id>", which must be one of the sandbox's tag_value_ids. Only
    valid with role_arn.
    """


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig(BaseModel):
    access_key_id: ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID

    secret_access_key: ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey

    role_arn: Optional[Literal[""]] = None
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


class ProxyConfigRuleAzureSandboxesProxyAzureWorkloadIdentityConfig(BaseModel):
    client_id: str
    """
    ClientID is the application (client) ID, a GUID, of the app registration or
    user-assigned managed identity whose federated identity credential trusts
    LangSmith's issuer. Required with tenant_id.
    """

    tenant_id: str
    """TenantID is the Entra tenant (directory) ID, a GUID.

    Setting it selects workload identity: LangSmith signs an OIDC token for this
    workspace and exchanges it at Entra ID for access tokens of client_id, so no
    secret is stored. Cannot be changed after creation.
    """

    resources: Optional[
        List[
            Literal[
                "https://storage.azure.com",
                "https://vault.azure.net",
                "https://management.azure.com",
                "https://cognitiveservices.azure.com",
            ]
        ]
    ] = None
    """
    Resources narrows the Entra resources access tokens are obtained for, from
    https://storage.azure.com, https://vault.azure.net, https://management.azure.com
    and https://cognitiveservices.azure.com. Defaults to all of them. Only valid
    with tenant_id.
    """

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the federated credential trusts:
    "workspace" (the default) or "tag:<tag value id>", which must be one of the
    sandbox's tag_value_ids. Only valid with tenant_id.
    """


class ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfigAccountKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfig(BaseModel):
    account_key: ProxyConfigRuleAzureSandboxesProxyAzureAccountKeyConfigAccountKey

    storage_account: str
    """
    StorageAccount is the storage account static credentials authenticate to:
    requests to its blob, dfs, queue, table and file endpoints. Requires exactly one
    of account_key (requests are signed with SharedKey) or sas_token (appended to
    each request).
    """


class ProxyConfigRuleAzureSandboxesProxyAzureSasConfigSasToken(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAzureSandboxesProxyAzureSasConfig(BaseModel):
    sas_token: ProxyConfigRuleAzureSandboxesProxyAzureSasConfigSasToken

    storage_account: str
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


class ProxyConfigRuleGcpServiceAccountJson(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleGcp(BaseModel):
    scopes: Optional[List[str]] = None
    """Scopes are the OAuth scopes requested for the access token.

    Omit them to use https://www.googleapis.com/auth/cloud-platform.
    """

    service_account_email: Optional[str] = None
    """
    ServiceAccountEmail is the service account to impersonate with the federated
    token. Omit it to use the federated principal directly.
    """

    service_account_json: Optional[ProxyConfigRuleGcpServiceAccountJson] = None

    subject_scope: Optional[str] = None
    """
    SubjectScope picks the token subject the provider trusts: "workspace" (the
    default) or "tag:<tag value id>", which must be one of the sandbox's
    tag_value_ids. Only valid with workload_identity_provider.
    """

    workload_identity_provider: Optional[str] = None
    """
    WorkloadIdentityProvider federates an OIDC token LangSmith signs for this
    workspace through Workload Identity Federation instead of a service account key.
    Use the full resource name:
    //iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>.
    Cannot be changed after creation.
    """


class ProxyConfigRuleHeader(BaseModel):
    name: str

    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRule(BaseModel):
    name: str

    aws: Optional[ProxyConfigRuleAws] = None

    azure: Optional[ProxyConfigRuleAzure] = None

    description: Optional[str] = None
    """
    Description says what this rule lets the sandbox reach, so an agent driving the
    sandbox can be told its capabilities. At most 1024 characters.
    """

    enabled: Optional[bool] = None

    env_vars: Optional[Dict[str, str]] = None
    """
    EnvVars are plaintext env vars set for every command in the sandbox while this
    rule is enabled. Use them for tools that refuse to run unless a credential env
    var is present (e.g. gh needs GH_TOKEN) even though this rule injects the real
    credential on the wire — set a dummy value here so the command starts. Explicit
    per-sandbox env_vars win over these, and provider-managed (AWS/GCP) vars win
    over both.
    """

    gcp: Optional[ProxyConfigRuleGcp] = None

    headers: Optional[List[ProxyConfigRuleHeader]] = None

    match_headers: Optional[List[str]] = None
    """
    MatchHeaders restricts a header injection rule to requests carrying every listed
    header, each written "name: value" with a lowercase name and an exact value.
    Pair with headers of the same name to swap a placeholder the sandbox sends (e.g.
    "authorization: Bearer account-b") for a real credential, so one host can serve
    several accounts. Rules are evaluated in order and the first match wins.
    """

    match_hosts: Optional[List[str]] = None
    """MatchHosts is only accepted for header injection rules.

    Provider auth rules use built-in host matching.
    """

    match_paths: Optional[List[str]] = None

    type: Optional[str] = None


class ProxyConfig(BaseModel):
    access_control: Optional[ProxyConfigAccessControl] = None

    callbacks: Optional[List[ProxyConfigCallback]] = None

    description: Optional[str] = None
    """
    Description says what this configuration as a whole lets the sandbox reach,
    complementing the per-rule descriptions. At most 1024 characters.
    """

    no_proxy: Optional[List[str]] = None

    rules: Optional[List[ProxyConfigRule]] = None


class RunConfig(BaseModel):
    """
    RunConfig is what the sandbox's commands run with: the user, working directory and base env beneath env_vars.
    """

    env_vars: Optional[Dict[str, str]] = None

    user: Optional[str] = None

    work_dir: Optional[str] = None


class SandboxResponse(BaseModel):
    id: Optional[str] = None

    access_delegation: Optional[AccessDelegation] = None
    """
    AccessDelegation is the LangSmith access this sandbox was granted, absent when
    it has none. It is reported exactly as it was requested at create.
    """

    cpu_millicores: Optional[int] = None

    created_at: Optional[str] = None

    created_by: Optional[str] = None

    dataplane_url: Optional[str] = None

    delete_after_stop_seconds: Optional[int] = None

    fs_capacity_bytes: Optional[int] = None

    idle_ttl_seconds: Optional[int] = None

    labels: Optional[Dict[str, str]] = None

    mem_bytes: Optional[int] = None

    mount_config: Optional[MountConfig] = None

    name: Optional[str] = None

    preserve_memory_on_stop: Optional[bool] = None

    proxy_config: Optional[ProxyConfig] = None

    run_config: Optional[RunConfig] = None
    """
    RunConfig is what the sandbox's commands run with: the user, working directory
    and base env beneath env_vars.
    """

    size_class: Optional[str] = None

    snapshot_id: Optional[str] = None

    status: Optional[str] = None

    status_message: Optional[str] = None

    stopped_at: Optional[str] = None

    updated_at: Optional[str] = None

    updated_by: Optional[str] = None

    vcpus: Optional[int] = None
