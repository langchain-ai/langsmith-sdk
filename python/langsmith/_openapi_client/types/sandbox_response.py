# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union, Optional
from typing_extensions import Literal, TypeAlias

from .._models import BaseModel

__all__ = [
    "SandboxResponse",
    "MountConfig",
    "MountConfigAuth",
    "MountConfigAuthAws",
    "MountConfigAuthAwsAccessKeyID",
    "MountConfigAuthAwsSecretAccessKey",
    "MountConfigAuthGcp",
    "MountConfigAuthGcpServiceAccountJson",
    "MountConfigMount",
    "MountConfigMountSandboxapiS3BucketMountSpec",
    "MountConfigMountSandboxapiS3BucketMountSpecS3",
    "MountConfigMountSandboxapiS3BucketMountSpecCache",
    "MountConfigMountSandboxapiS3BucketMountSpecGcs",
    "MountConfigMountSandboxapiS3BucketMountSpecGit",
    "MountConfigMountSandboxapiS3BucketMountSpecGitRef",
    "MountConfigMountSandboxapiGcsBucketMountSpec",
    "MountConfigMountSandboxapiGcsBucketMountSpecGcs",
    "MountConfigMountSandboxapiGcsBucketMountSpecCache",
    "MountConfigMountSandboxapiGcsBucketMountSpecGit",
    "MountConfigMountSandboxapiGcsBucketMountSpecGitRef",
    "MountConfigMountSandboxapiGcsBucketMountSpecS3",
    "MountConfigMountSandboxapiGitRepoMountSpec",
    "MountConfigMountSandboxapiGitRepoMountSpecGit",
    "MountConfigMountSandboxapiGitRepoMountSpecGitRef",
    "MountConfigMountSandboxapiGitRepoMountSpecCache",
    "MountConfigMountSandboxapiGitRepoMountSpecGcs",
    "MountConfigMountSandboxapiGitRepoMountSpecS3",
    "ProxyConfig",
    "ProxyConfigAccessControl",
    "ProxyConfigCallback",
    "ProxyConfigCallbackRequestHeader",
    "ProxyConfigRule",
    "ProxyConfigRuleAws",
    "ProxyConfigRuleAwsAccessKeyID",
    "ProxyConfigRuleAwsSecretAccessKey",
    "ProxyConfigRuleGcp",
    "ProxyConfigRuleGcpServiceAccountJson",
    "ProxyConfigRuleHeader",
]


class MountConfigAuthAwsAccessKeyID(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAwsSecretAccessKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthAws(BaseModel):
    access_key_id: MountConfigAuthAwsAccessKeyID

    secret_access_key: MountConfigAuthAwsSecretAccessKey


class MountConfigAuthGcpServiceAccountJson(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class MountConfigAuthGcp(BaseModel):
    service_account_json: MountConfigAuthGcpServiceAccountJson


class MountConfigAuth(BaseModel):
    aws: Optional[MountConfigAuthAws] = None

    gcp: Optional[MountConfigAuthGcp] = None


class MountConfigMountSandboxapiS3BucketMountSpecS3(BaseModel):
    bucket: str

    region: str

    endpoint_url: Optional[str] = None

    path_style: Optional[bool] = None

    prefix: Optional[str] = None


class MountConfigMountSandboxapiS3BucketMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


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

    type: Literal["s3", "gcs", "git"]

    cache: Optional[MountConfigMountSandboxapiS3BucketMountSpecCache] = None

    gcs: Optional[MountConfigMountSandboxapiS3BucketMountSpecGcs] = None

    git: Optional[MountConfigMountSandboxapiS3BucketMountSpecGit] = None

    read_only: Optional[bool] = None


class MountConfigMountSandboxapiGcsBucketMountSpecGcs(BaseModel):
    bucket: str

    prefix: Optional[str] = None


class MountConfigMountSandboxapiGcsBucketMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


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

    type: Literal["s3", "gcs", "git"]

    cache: Optional[MountConfigMountSandboxapiGcsBucketMountSpecCache] = None

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


class MountConfigMountSandboxapiGitRepoMountSpecCache(BaseModel):
    max_size_bytes: Optional[int] = None

    writeback_seconds: Optional[int] = None


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

    type: Literal["s3", "gcs", "git"]

    cache: Optional[MountConfigMountSandboxapiGitRepoMountSpecCache] = None

    gcs: Optional[MountConfigMountSandboxapiGitRepoMountSpecGcs] = None

    read_only: Optional[bool] = None

    s3: Optional[MountConfigMountSandboxapiGitRepoMountSpecS3] = None


MountConfigMount: TypeAlias = Union[
    MountConfigMountSandboxapiS3BucketMountSpec,
    MountConfigMountSandboxapiGcsBucketMountSpec,
    MountConfigMountSandboxapiGitRepoMountSpec,
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


class ProxyConfigRuleAwsAccessKeyID(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAwsSecretAccessKey(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleAws(BaseModel):
    access_key_id: ProxyConfigRuleAwsAccessKeyID

    secret_access_key: ProxyConfigRuleAwsSecretAccessKey


class ProxyConfigRuleGcpServiceAccountJson(BaseModel):
    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRuleGcp(BaseModel):
    scopes: List[str]

    service_account_json: ProxyConfigRuleGcpServiceAccountJson


class ProxyConfigRuleHeader(BaseModel):
    name: str

    type: Literal["plaintext", "opaque", "workspace_secret"]

    is_set: Optional[bool] = None

    value: Optional[str] = None


class ProxyConfigRule(BaseModel):
    name: str

    aws: Optional[ProxyConfigRuleAws] = None

    enabled: Optional[bool] = None

    gcp: Optional[ProxyConfigRuleGcp] = None

    headers: Optional[List[ProxyConfigRuleHeader]] = None

    match_hosts: Optional[List[str]] = None
    """MatchHosts is only accepted for header injection rules.

    Provider auth rules use built-in host matching.
    """

    match_paths: Optional[List[str]] = None

    type: Optional[str] = None


class ProxyConfig(BaseModel):
    access_control: Optional[ProxyConfigAccessControl] = None

    callbacks: Optional[List[ProxyConfigCallback]] = None

    no_proxy: Optional[List[str]] = None

    rules: Optional[List[ProxyConfigRule]] = None


class SandboxResponse(BaseModel):
    id: Optional[str] = None

    created_at: Optional[str] = None

    created_by: Optional[str] = None

    dataplane_url: Optional[str] = None

    delete_after_stop_seconds: Optional[int] = None

    fs_capacity_bytes: Optional[int] = None

    idle_ttl_seconds: Optional[int] = None

    mem_bytes: Optional[int] = None

    mount_config: Optional[MountConfig] = None

    name: Optional[str] = None

    proxy_config: Optional[ProxyConfig] = None

    size_class: Optional[str] = None

    snapshot_id: Optional[str] = None

    status: Optional[str] = None

    status_message: Optional[str] = None

    stopped_at: Optional[str] = None

    updated_at: Optional[str] = None

    updated_by: Optional[str] = None

    vcpus: Optional[int] = None
