# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from ..._types import SequenceNotStr

__all__ = [
    "BoxCreateParams",
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


class BoxCreateParams(TypedDict, total=False):
    delete_after_stop_seconds: int

    env_vars: Dict[str, str]

    fs_capacity_bytes: int

    idle_ttl_seconds: int

    mem_bytes: int

    mount_config: MountConfig

    name: str

    proxy_config: ProxyConfig

    restore_memory: bool
    """RestoreMemory selects how the sandbox handles a snapshot's captured memory:

    nil → if-present: resume from memory when the snapshot has it, else cold-boot
    (default). true → always: resume from memory; rejected if the snapshot has none.
    false → never: always cold-boot.

    Applies to this request only.
    """

    snapshot_id: str

    snapshot_name: str

    tag_value_ids: SequenceNotStr[str]

    vcpus: int


class MountConfigAuthAwsAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAwsSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthAws(TypedDict, total=False):
    access_key_id: Required[MountConfigAuthAwsAccessKeyID]

    secret_access_key: Required[MountConfigAuthAwsSecretAccessKey]


class MountConfigAuthGcpServiceAccountJson(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class MountConfigAuthGcp(TypedDict, total=False):
    service_account_json: Required[MountConfigAuthGcpServiceAccountJson]


class MountConfigAuth(TypedDict, total=False):
    aws: MountConfigAuthAws

    gcp: MountConfigAuthGcp


class MountConfigMountSandboxapiS3BucketMountSpecS3(TypedDict, total=False):
    bucket: Required[str]

    region: Required[str]

    endpoint_url: str

    path_style: bool

    prefix: str


class MountConfigMountSandboxapiS3BucketMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


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

    type: Required[Literal["s3", "gcs", "git"]]

    cache: MountConfigMountSandboxapiS3BucketMountSpecCache

    gcs: MountConfigMountSandboxapiS3BucketMountSpecGcs

    git: MountConfigMountSandboxapiS3BucketMountSpecGit

    read_only: bool


class MountConfigMountSandboxapiGcsBucketMountSpecGcs(TypedDict, total=False):
    bucket: Required[str]

    prefix: str


class MountConfigMountSandboxapiGcsBucketMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


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

    type: Required[Literal["s3", "gcs", "git"]]

    cache: MountConfigMountSandboxapiGcsBucketMountSpecCache

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


class MountConfigMountSandboxapiGitRepoMountSpecCache(TypedDict, total=False):
    max_size_bytes: int

    writeback_seconds: int


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

    type: Required[Literal["s3", "gcs", "git"]]

    cache: MountConfigMountSandboxapiGitRepoMountSpecCache

    gcs: MountConfigMountSandboxapiGitRepoMountSpecGcs

    read_only: bool

    s3: MountConfigMountSandboxapiGitRepoMountSpecS3


MountConfigMount: TypeAlias = Union[
    MountConfigMountSandboxapiS3BucketMountSpec,
    MountConfigMountSandboxapiGcsBucketMountSpec,
    MountConfigMountSandboxapiGitRepoMountSpec,
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


class ProxyConfigRuleAwsAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAws(TypedDict, total=False):
    access_key_id: Required[ProxyConfigRuleAwsAccessKeyID]

    secret_access_key: Required[ProxyConfigRuleAwsSecretAccessKey]


class ProxyConfigRuleGcpServiceAccountJson(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleGcp(TypedDict, total=False):
    scopes: Required[SequenceNotStr[str]]

    service_account_json: Required[ProxyConfigRuleGcpServiceAccountJson]


class ProxyConfigRuleHeader(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRule(TypedDict, total=False):
    name: Required[str]

    aws: ProxyConfigRuleAws

    enabled: bool

    gcp: ProxyConfigRuleGcp

    headers: Iterable[ProxyConfigRuleHeader]

    match_hosts: SequenceNotStr[str]
    """MatchHosts is only accepted for header injection rules.

    Provider auth rules use built-in host matching.
    """

    match_paths: SequenceNotStr[str]

    type: str


class ProxyConfig(TypedDict, total=False):
    access_control: ProxyConfigAccessControl

    callbacks: Iterable[ProxyConfigCallback]

    no_proxy: SequenceNotStr[str]

    rules: Iterable[ProxyConfigRule]
