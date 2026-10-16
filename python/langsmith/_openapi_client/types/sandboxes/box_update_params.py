# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, List, Union, Iterable
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = [
    "BoxUpdateParams",
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


class BoxUpdateParams(TypedDict, total=False):
    cpu_millicores: int

    delete_after_stop_seconds: int

    fs_capacity_bytes: int

    idle_ttl_seconds: int

    mem_bytes: int
    """New memory for the sandbox, in bytes.

    The 4 GiB per vCPU ratio applies when the sandbox is created; a resize enforces
    only the maximum of 64 GiB.
    """

    body_name: Annotated[str, PropertyInfo(alias="name")]

    proxy_config: ProxyConfig

    run_config: RunConfig
    """
    RunConfig changes what subsequent commands run with: user and work_dir replace
    the current values, env_vars merge over them. Commands already running are
    unaffected.
    """

    tag_value_ids: SequenceNotStr[str]

    vcpus: int


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
    RunConfig changes what subsequent commands run with: user and work_dir
    replace the current values, env_vars merge over them. Commands already
    running are unaffected.
    """

    env_vars: Dict[str, str]

    user: str

    work_dir: str
